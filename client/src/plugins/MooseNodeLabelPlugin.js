/* ------------------------------------------------------------------------- *
 *  Copyright (c) 2011-2023 Proofscape Contributors                          *
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


import {PdfLabelRenderer} from "./PdfLabelRenderer";

/* This class implements the necessary interface to serve as a
 * "node label plugin" for Moose.
 *
 * This means an instance can be passed to a Moose Forest, and then it will
 * be given a chance to do any custom processing on node labels whenever new
 * node labels are constructed.
 */
export class MooseNodeLabelPlugin {

    constructor(hub) {
        this.hub = hub;
        this.pdfLabelRenderer = new PdfLabelRenderer(this.hub.pdfManager);
    }

    /* This method constitutes the whole Moose node label plugin interface.
     * Moose will pass node label divs whenever they are being constructed,
     * after the typesetting step.
     * We get a chance to do whatever custom processing we need to do.
     *
     * @param nodeDivs: Map from Node libpaths to the divs that will make
     *   these Nodes' labels.
     * @return: promise that resolves when we are done processing labels.
     */
    processLabels(nodeDivs) {
        const jobs = [];
        let allPdfDivs = [];
        for (let [nodepath, labeldiv] of nodeDivs) {
            // Activate links.
            const annolinks = labeldiv.querySelectorAll('.annolink');
            if (annolinks.length) this.activateAnnolinks(annolinks);
            const extlinks = labeldiv.querySelectorAll('a.external');
            if (extlinks.length) this.setupExternalLinks(extlinks);

            // Gather PDF labels.
            const pdfDivNodeList = labeldiv.querySelectorAll('div.doc-render');
            allPdfDivs = allPdfDivs.concat(Array.from(pdfDivNodeList));
        }
        // Process all PDF labels at once.
        jobs.push(this.pdfLabelRenderer.render(allPdfDivs));

        return Promise.all(jobs);
    }

    activateAnnolinks(annolinks) {
        //console.log('activate annolinks', annolinks);
        for (let annolink of annolinks) {
            const infoNode = annolink.querySelector('.annolinkInfo');
            const infoText = infoNode.innerText;
            const info = JSON.parse(infoText);
            const widget = this.hub.notesManager.constructWidget(info);
            annolink.addEventListener('click', widget.onClick.bind(widget));
        }
    }

    setupExternalLinks(extlinks) {
        // For external links it's important that we stop propagation of the click
        // event (a) because we don't want the node to become selected due to this click,
        // and (b) because subsequent handlers (i.e. in pfsc-moose code) may call
        // the event's `preventDefault()` method, telling the browser not to do the default
        // action on this `<a>` tag, which we actually do want it to do.
        for (let extlink of extlinks) {
            extlink.addEventListener('click', e => e.stopPropagation());
        }
    }

}
