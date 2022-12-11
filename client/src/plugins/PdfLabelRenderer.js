/* ------------------------------------------------------------------------- *
 *  Copyright (c) 2011-2022 Proofscape contributors                          *
 *                                                                           *
 *  Licensed under the Apache License, Version 2.0 (the "License");          *
 *  you may not use this file except in compliance with the License.         *
 *  You may obtain a copy of the License at                                  *
 *                                                                           *
 *      http://www.apache.org/licenses/LICENSE-2.0                           *
 *                                                                           *
 *  Unless required by applicable law or agreed to in writing, software      *
 *  distributed under the License is distributed on an "AS IS" BASIS,        *
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. *
 *  See the License for the specific language governing permissions and      *
 *  limitations under the License.                                           *
 * ------------------------------------------------------------------------- */

const ise = {};
define([
    "ise/content_types/pdf/pdf_util",
    "ise/util"
], function(
    pdf_util,
    util
){
    ise.pdf_util = pdf_util;
    ise.util = util;
});

/* This class supports the MooseNodeLabelPlugin by providing the tools
 * to render PDF labels for nodes.
 */
export class PdfLabelRenderer {

    constructor(pdfManager) {
        this.pdfManager = pdfManager;

        // After some experimentation, a rendering scale of 4 seems to be a good choice.
        // Lower values make for fuzzy labels, even at moderate zoom levels in the chart.
        // Higher values would smooth out the characters even more, but we do have to watch
        // out for the maximum number of pixels allowed in a canvas.
        // Since 400% is the maximum zoom setting available in Mozilla's generic viewer
        // interface, that seems like a good place to stop.
        this.renderingScale = 4;
    }

    /* Render PDF labels for PDF label divs.
     *
     * @param pdfDivs: Array of divs that must be of the form:
     *
     *   <div class="pdf-render" data-pdf-fingerprint="${fp}" data-pdf-combinercode="${code}"></div>
     *
     * @return: Promise that resolves when rendering is done.
     */
    render(pdfDivs) {
        const f2c2d = this.buildMapping(pdfDivs);
        // We make a first attempt to render. This time, if any PDF is unavailable, we simply
        // ask for blank canvases of the right size.
        const non_waiting_jobs = this.tryToRender(f2c2d, f2c2d.keys(), false);
        return Promise.all(non_waiting_jobs).then(results => {
            const missingFps = results.filter(r => r.missing).map(r => r.fingerprint);
            if (missingFps.length) {
                // Make a second attempt to render, just with those PDFs that were missing the first
                // time. This time, we ask to wait indefinitely on those PDFs. Our function call returns
                // synchronously though, and we simply don't chain any activity off of its resolution.
                // We leave it to resolve on its own, if ever, while we go about our business.
                this.tryToRender(f2c2d, missingFps, true);
            }
            // In case it is useful, we return the array of missing fingerprints.
            return missingFps;
        });
    }

    /* Build an "fps2codes2divs" mapping for a given set of "PDF divs".
     *
     * The mapping sends each fingerprint to a map sending each combiner code to an Array of divs
     * that want this fp-code combination.
     *
     * The divs look like:
     *
     *   <div class="pdf-render" data-pdf-fingerprint="${fp}" data-pdf-combinercode="${code}"></div>
     *
     * and represent a desired PDF-based label for a node.
     *
     * Note a couple of subtleties:
     *
     * (1) Although quite unlikely, the same combiner code _could_ be desired from within two different
     * PDF docs. This is why we cannot simply maps codes to divs; the codes must be classified under the
     * fingerprints to which they pertain.
     *
     * (2) Quite a bit more likely, two node divs could want exactly the same label. (E.g. maybe two nodes in
     * a proof both say $p < q$?) So we have to keep an _Array_ of divs that want a given fp-code combination.
     *
     * @param pdfDivs: Array of divs wanting PDF labels.
     * @return: map from fingerprints to maps from codes to arrays of divs.
     */
    buildMapping(pdfDivs) {
        const fps2codes2divs = new Map();
        for (let pdfDiv of pdfDivs) {
            const fp = pdfDiv.getAttribute('data-pdf-fingerprint');
            const code = pdfDiv.getAttribute('data-pdf-combinercode');
            if (fp === null || code === null) {
                console.error(`Malformed pdf label div`, pdfDiv);
                continue;
            }
            const m = fps2codes2divs.get(fp) || new Map();
            const a = m.get(code) || [];
            a.push(pdfDiv);
            m.set(code, a);
            fps2codes2divs.set(fp, m);
        }
        return fps2codes2divs;
    }

    /* Get a PDF pane featuring the PDF identified by a given fingerprint.
     *
     * @param fp {string} the desired fingerprint.
     * @param wait {boolean} if true, we will wait indefinitely for the desired PDF pane;
     *   if false, and the PDF we want is not available right now, resolve now with `null`.
     * @return: promise that resolves with a ContentPane, or `null`.
     *
     * Note: For now, an "available" PDF means one that's available in _this_ window.
     * In the future we may support the case where the PDF has become available in a different
     * window. Stay tuned...
     */
    getPaneForFingerprint(fp, wait = true) {
        return new Promise(resolve => {
            const panes = this.pdfManager.findPanesByFingerprint(fp);
            if (panes.length > 0) {
                resolve(panes[0]);
            } else if (!wait) {
                resolve(null);
            } else {
                const wm = this.pdfManager.hub.windowManager;
                const panesById = this.pdfManager.panesById;
                const handleFpAvailable = event => {
                    if (event.fingerprint === fp) {
                        // Get number inside event handler, since could have changed while waiting.
                        const {myNumber} = wm.getNumbers();
                        if (event.windowNumber === myNumber) {
                            const pane = panesById[event.paneId];
                            wm.off('pdfFingerprintAvailable', handleFpAvailable);
                            resolve(pane);
                        } else {
                            // Experimental attempt to open the PDF in this window, in hopes
                            // of then being able to resolve:
                            //this.hub.contentManager.openContentInActiveTC(event.origInfo);
                            // Maybe should do this only if event.origInfo defines a URL?
                            // Can't do the case where the PDF was opened from the user's
                            // computer, since that would require sending non-serializable
                            // info (or else asking the other window for the whole byte array,
                            // which is possible but might be very slow??? Need to test....).
                        }
                    }
                };
                wm.on('pdfFingerprintAvailable', handleFpAvailable);
            }
        });
    }

    /* We're going to need to "try to render" twice (potentially).
     *
     * @param f2c2d: a fingerprints-to-codes-to-divs mapping (see above).
     * @param fps {Array[string]} the fingerprints for which we want to attempt rendering.
     * @param wait {boolean} to be passed to `getPaneForFingerprint` (see above).
     * @return: Array of promises, one for each fingerprint in `fps`. Each promise
     *   resolves with an object of the form: {
     *      fingerprint: {string},
     *      missing: {boolean},
     *   } indicating whether its fingerprint was missing or not.
     */
    tryToRender(f2c2d, fps, wait) {
        const jobs = [];
        for (let fp of fps) {
            const codes2divs = f2c2d.get(fp);
            const job = this.getPaneForFingerprint(fp, wait).then(pane => {
                const info = {
                    fingerprint: fp,
                    missing: pane === null,
                };
                return this.makeAndSetLabels(codes2divs, pane, fp).then(() => info);
            });
            jobs.push(job);
        }
        return jobs;
    }

    /* Make the labels for a given set of divs, and set them in place.
     *
     * @param codes2divs: Map from combiner codes, each specifying the desired
     *   combination of boxes for a single canvas, to Arrays of divs that want
     *   that canvas as their label.
     * @param pdfPane: either a ContentPane holding the PDF in which the desired
     *   content is to be found, or `null` if no such pane was available.
     * @param fingerprint: the fingerprint of the PDF in question.
     * @return: promise that resolves when the job is complete.
     */
    makeAndSetLabels(codes2divs, pdfPane, fingerprint) {
        // FIXME: Should we cancel if the divs do not belong to the document?
        //   (Imagining we'd test this with `document.body.contains(elt)`.)
        //   It seems tricky because we don't know the difference between divs
        //   that are _no longer_ in the doc, vs those that are _not yet_ in it.
        //   "No longer" will be quite common, arising if (1) a chart was opened
        //   while the PDF was unavailable; (2) the chart pane was closed; (3) the
        //   PDF became available. In such a case, this method represents wasted effort.
        //   However, "not yet" could happen if instead (1) and (3) happened in
        //   rapid succession (and (2) didn't happen at all). Then canceling would
        //   prevent those labels from ever being rendered.
        const codes = Array.from(codes2divs.keys());
        return this.renderCanvases(codes, pdfPane).then(codes2canvases => {
            const missing = pdfPane === null;
            const pdfManager = this.pdfManager;
            let learnMoreHtml;
            let learnMoreHandler;
            if (missing) {
                learnMoreHtml = `
                    <div class="pdfLearnMore">
                        <a href="#">(PDF)</a>
                    </div>
                `;
                learnMoreHandler = () => {
                    const message = 'To render this node label you need to open the PDF:';
                    pdfManager.showPdfMissingDialog(message, fingerprint);
                };
            }
            for (let [code, canvas] of codes2canvases) {
                const divs = codes2divs.get(code);
                for (let div of divs) {
                    // Clear any prior contents.
                    ise.util.removeAllChildNodes(div);
                    if (missing) {
                        div.innerHTML = learnMoreHtml;
                        const lm = div.querySelector('.pdfLearnMore');
                        lm.style.width = canvas.style.width;
                        lm.style.height = canvas.style.height;
                        lm.querySelector('a').addEventListener('click', learnMoreHandler);
                    } else {
                        const c = canvas.cloneNode();
                        // Cloning the node doesn't reproduce the drawing on the canvas.
                        // For that, need a bit more.
                        const destCtx = c.getContext('2d');
                        destCtx.drawImage(canvas, 0, 0);
                        div.appendChild(c);
                    }
                }
            }
        });
    }

    /* Render a set of canvases.
     *
     * @param codes: Array of combiner codes.
     * @param pdfPane: either a ContentPane holding the PDF in which the desired
     *   content is to be found, or `null` if no such pane was available.
     * @return: promise that resolves with a map from codes to canvases.
     *   The canvases will be blank if pdfPane was `null`; otherwise they
     *   will show the desired content.
     */
    renderCanvases(codes, pdfPane) {
        // Make a single, giant lookup of all boxes for all codes.
        // They can all be rendered at once.
        const Bi = ise.pdf_util.makeAllBoxesFromCombinerCodes(codes);

        const boxesByDescrip = {};
        Bi.forEach(box => {
            boxesByDescrip[box.writeDescription()] = box;
        });

        const scale = this.renderingScale;
        const renderingPromise = new Promise((resolve, reject) => {
            if (pdfPane === null) {
                resolve();
            } else {
                const pdfc = this.pdfManager.getPdfcForPane(pdfPane);
                pdfc.renderBoxes(Bi, scale).then(resolve);
            }
        });

        // After the box contents have been retrieved from the PDF document (or not),
        // we can assemble the canvas elements.
        return renderingPromise.then(function() {
            const codes2canvases = new Map();
            codes.forEach(code => {
                const canvas = document.createElement('canvas');
                const prog = ise.pdf_util.parseCombinerCode(code, boxesByDescrip);
                const renderingZoom = prog.getRenderingZoom();
                prog.scaleShifts(renderingZoom);
                const defTimeZoom = prog.scale;
                const displayScaling = 1/(defTimeZoom * renderingZoom);
                ise.pdf_util.renderProgram(prog, canvas, displayScaling);
                codes2canvases.set(code, canvas);
            });
            return codes2canvases;
        });
    }

}
