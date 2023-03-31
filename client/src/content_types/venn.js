/* ------------------------------------------------------------------------- *
 *  Copyright (c) 2011-2023 Proofscape contributors                          *
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

const dojo = {};
const ise = {};

define([
    "dijit/Menu",
    "dijit/MenuItem",
    "ise/content_types/pdf/pdf_util",
    "ise/util"
], function(
    Menu,
    MenuItem,
    pdf_util,
    iseUtil
) {
    dojo.Menu = Menu;
    dojo.MenuItem = MenuItem;
    ise.pdf_util = pdf_util;
    ise.util = iseUtil;
});

/* This module solves the problem of multiple, intersecting highlights on a
 * given page of a document.
 *
 * A highlight is a union of boxes. When we speak of computing the "Venn diagram"
 * for a collection of highlights, we mean that we want to compute all the
 * intersections of all these boxes, resulting in a "refined" set of rectangles, which
 * are pairwise disjoint, but whose union equals the union of the original highlights.
 *
 * We refer to the refined rectangles as "regions". So, a Venn diagram consists of
 * a collection of disjoint regions.
 *
 * We have a Highlight class, and a Region class. After refinement, each Region is
 * aware of all the Highlights to which it belongs, and each Highlight is aware of
 * all the Regions that belong to it.
 *
 * We also have a Page class, and the notion of a "zone". A single highlight can
 * span multiple pages. We refer to the portion of a highlight belonging to a single
 * page as a "zone" of that highlight. Venn diagrams are only computed one page
 * at a time, i.e. for the highlight zones that land on that page.
 *
 * Just for future reference, there are SVG methods like `getIntersectionList` that you
 * might consider employing for such applications, but (a) these methods are not currently
 * supported by all browsers (namely Firefox; see
 *   https://developer.mozilla.org/en-US/docs/Web/API/SVGSVGElement#browser_compatibility
 *   https://bugzilla.mozilla.org/show_bug.cgi?id=501421
 * ),
 * and (b) our method has the advantage of computing the intersections once and for all,
 * and therefore saving computation costs if such intersections matter (as they do in our
 * application!) on events like `mouseover` that can happen many times in rapid succession.
 */

// A collection of boxes, potentially spanning multiple pages.
export class Highlight {
    
    constructor(documentController, highlightDescriptor) {
        this.documentController = documentController;
        this.highlightDescriptorsBySlp = new Map();
        this.highlightId = ise.util.extractOriginalHlidFromHlDescriptor(highlightDescriptor);
        this.depthsByPageNum = new Map();
        this.selectionBoxesByPageNum = new Map();
        this.refinedRegionsByPageNum = new Map();
        this.zoneDivsByPageNum = new Map();
        this.supplierMenu = new dojo.Menu({
            leftClickToOpen: true,
            disabled: true,
        });

        this.addSupplier(highlightDescriptor);

        // Turn the highlight's combiner code into a collection of
        // SelectionBoxes, sorted by page number.
        const ccode = highlightDescriptor.ccode;
        const selectionBoxes = ise.pdf_util.makeAllBoxesFromCombinerCodes([ccode]);
        for (const selBox of selectionBoxes) {
            const p = selBox.pageNumber;
            if (!this.selectionBoxesByPageNum.has(p)) {
                this.selectionBoxesByPageNum.set(p, []);
            }
            this.selectionBoxesByPageNum.get(p).push(selBox);
        }

        // Determine the depth for each page.
        const pages = Array.from(this.selectionBoxesByPageNum.keys()).sort();
        const p0 = pages[0];
        const prog = ise.pdf_util.parseCombinerCode(ccode, null);
        const depths = prog.depths;
        for (const p of pages) {
            this.depthsByPageNum.set(p, depths[p - p0] || 0);
        }

    }

    // Add a new supplier, by its highlight descriptor.
    addSupplier(hdo) {
        this.highlightDescriptorsBySlp.set(hdo.slp, hdo);
        this.redoSupplierMenu();
    }

    // Remove and return a highlight supplier's descriptor.
    popSupplier(slp) {
        const hdo = this.highlightDescriptorsBySlp.get(slp);
        this.highlightDescriptorsBySlp.delete(slp);
        this.redoSupplierMenu();
        return hdo;
    }

    // Check how many highlight suppliers this highlight has.
    getSupplierCount() {
        return this.highlightDescriptorsBySlp.size;
    }

    // If we have exactly one supplier, get its HDO; else null.
    getSingletonSupplier() {
        const hdos = Array.from(this.highlightDescriptorsBySlp.values());
        if (hdos.length === 1) {
            return hdos[0];
        }
        return null;
    }

    // List the page numbers on which this highlight has presence.
    listPageNums() {
        return Array.from(this.selectionBoxesByPageNum.keys()).sort();
    }

    // Get the number of the first page on which this highlight has presence.
    firstPage() {
        const pageNums = this.listPageNums();
        return Math.min(...pageNums);
    }

    // Given the size of a rendered page, produce the initial regions for
    // that page, for this highlight. There is one initial region for each
    // box making up the highlight.
    buildInitialRegionsForRenderedPage(pageNum, pageWidth) {
        const selBoxes = this.selectionBoxesByPageNum.get(pageNum) || [];
        const scaledBoxes = selBoxes.map(box => box.makeRoundedScaledCopy(pageWidth/box.W));
        const hls = new Set([this]);
        return scaledBoxes.map(b => new Region(
            b.x, b.x + b.w, b.y, b.y + b.h, hls
        ));
    }

    // Dump all existing graphical elements for a single given page.
    clearGraphicalElementsForPage(pageNum) {
        this.refinedRegionsByPageNum.set(pageNum, []);
        const div = this.zoneDivsByPageNum.get(pageNum);
        this.supplierMenu.unBindDomNode(div);
        this.zoneDivsByPageNum.delete(pageNum);
    }

    // After all highlights for a page have been combined and their regions
    // refined, this method can be used to tell this highlight about the refined regions.
    addRefinedRegionForPage(region, pageNum) {
        this.refinedRegionsByPageNum.get(pageNum).push(region);
    }

    // Say whether our zone on a given page is completely shared, i.e. every one of
    // its refined regions is a shared region.
    zoneIsCompletelyShared(pageNum) {
        return this.refinedRegionsByPageNum.get(pageNum).every(r => r.isShared());
    }

    // Say how many regions are in the zone on a given page.
    zoneRegionCount(pageNum) {
        return this.refinedRegionsByPageNum.get(pageNum).length;
    }

    // Report the surface area of the zone on a given page.
    zoneArea(pageNum) {
        return this.refinedRegionsByPageNum.get(pageNum).reduce(
            (acc, curr) => acc + curr.area(), 0
        );
    }

    // Compute the "impact" measure of the zone on a given page.
    zoneImpact(pageNum) {
        return this.refinedRegionsByPageNum.get(pageNum).reduce(
            (acc, curr) => acc + Math.log(curr.contestednessVersus(this, pageNum)), 0
        );
    }

    // Try to take sole-ownership of a shared region in which our zone on a
    // given page participates.
    //
    // We try to choose a region of minimal contestedness.
    //
    // If no regions are as yet unassigned, fail gracefully.
    //
    // return: the Region chosen, or null
    claimASharedRegion(pageNum) {
        let choice = null;
        let bestScore = -1;
        const regions = this.refinedRegionsByPageNum.get(pageNum);
        for (const r of regions) {
            if (!r.isClaimed()) {
                const c = r.contestednessVersus(this, pageNum);
                if (bestScore < 0 || c < bestScore) {
                    choice = r;
                    bestScore = c;
                }
            }
        }
        if (choice) {
            choice.claim(this);
        }
        return choice;
    }

    // Set/unset a temp color on all zones.
    // b: true to add the color class, false to remove it
    // n: the number of the color class (0 through 3)
    setTempColor(b, n) {
        const className = `temp-color-${n}`;
        for (let zoneDiv of this.zoneDivsByPageNum.values()) {
            if (b) {
                zoneDiv.classList.add(className);
            } else {
                zoneDiv.classList.remove(className);
            }
        }
    }

    // Clear any temporary colors that may have been set on this highlight.
    clearAllTempColors() {
        for (let n = 0; n < 4; n++) {
            this.setTempColor(false, n);
        }
    }

    // Set/unset selected class on all zones.
    // b: true to make selected, false to remove
    select(b) {
        const className = 'selected';
        for (let zoneDiv of this.zoneDivsByPageNum.values()) {
            if (b) {
                zoneDiv.classList.add(className);
            } else {
                zoneDiv.classList.remove(className);
            }
        }
        this.documentController.noteSelectedHighlight(this);
    }

    /* Return a document element to which the doc controller should scroll, in order
     * to bring this highlight into view, or null.
     *
     * return: a doc element having a non-null offsetParent, or null if we do not
     *   currently have such an element to offer.
     */
    getScrollElement() {
        let elt = null;
        const firstZone = this.zoneDivsByPageNum.get(this.firstPage());
        if (firstZone) {
            const firstRegion = firstZone.querySelector('.hl-region');
            // Check that the element has an offsetParent. It will not if it has been removed from
            // the document. This case arises when the page has been unloaded by the document
            // controller, while we still retain our reference to the element.
            if (firstRegion && firstRegion.offsetParent) {
                elt = firstRegion;
            }
        }
        return elt;
    }

    // Redo the supplier menu, based on our latest set of suppliers.
    redoSupplierMenu() {
        const menu = this.supplierMenu;
        const n = this.getSupplierCount();
        menu.set('disabled', n < 2);
        menu.destroyDescendants();
        if (n >= 2) {
            const hl = this;
            for (const hdo of this.highlightDescriptorsBySlp.values()) {
                (hdo => {
                    const hlid = ise.util.extractHlidFromHlDescriptor(hdo);
                    menu.addChild(new dojo.MenuItem({
                        // TODO: improve label
                        //  Should be human readable description
                        label: hlid,
                        onClick: function(event) {
                            hl.registerClick(event);
                            hl.handleMouseEvent(event, hdo);
                        },
                        onMouseOver: function(event) {
                            hl.handleMouseEvent(event, hdo);
                        },
                        onMouseOut: function(event) {
                            hl.handleMouseEvent(event, hdo);
                        },
                    }));
                })(hdo);
            }
            for (const zoneDiv of this.zoneDivsByPageNum.values()) {
                zoneDiv.classList.add('hl-multi');
            }
        } else {
            for (const zoneDiv of this.zoneDivsByPageNum.values()) {
                zoneDiv.classList.remove('hl-multi');
            }
        }
    }

    // Build the div that will represent our zone on a given page graphically,
    // and will receive mouse events.
    buildZoneDiv(pageNum) {
        const div = document.createElement('div');
        div.classList.add('hl-zone');
        for (const region of this.refinedRegionsByPageNum.get(pageNum) || []) {
            div.appendChild(region.buildDiv());
        }

        div.addEventListener('mouseover', event => {
            this.setTempColor(true, 0);
            const hdo = this.getSingletonSupplier();
            if (hdo) {
                this.handleMouseEvent(event, hdo);
            }
        });
        div.addEventListener('mouseout', event => {
            this.setTempColor(false, 0);
            const hdo = this.getSingletonSupplier();
            if (hdo) {
                this.handleMouseEvent(event, hdo);
            }
        });
        div.addEventListener('click', event => {
            const hdo = this.getSingletonSupplier();
            if (hdo) {
                this.registerClick(event);
                this.handleMouseEvent(event, hdo);
            }
        });

        this.supplierMenu.bindDomNode(div);

        this.zoneDivsByPageNum.set(pageNum, div);
        return div;
    }

    registerClick(event) {
        this.documentController.clearNamedHighlight();
        this.clearAllTempColors();
        this.select(true);
        event.stopPropagation();
    }

    handleMouseEvent(event, hdo) {
        this.documentController.handleHighlightMouseEvent(
            event, hdo
        );
    }

}


// A single Venn diagram region, among all the boxes on a single page.
class Region {
    
    /* x: min x coord
     * X: max X coord
     * y: min y coord
     * Y: max y coord
     * highlights: Set of Highlight instances to which this region belongs
     */
    constructor(x, X, y, Y, highlights) {
        this.x = x;
        this.X = X;
        this.y = y;
        this.Y = Y;
        this.highlights = highlights || new Set();
        this.claimedBy = null;
    }

    area() {
        return (this.X - this.x)*(this.Y - this.y);
    }

    /* Compute the "contestedness" score for this region, versus one zone z0 in
     * which it participates.
     *
     * See `compareCompletelySharedZones()` function regarding the definition
     * of "contestedness".
     *
     * param hl: the Highlight instance to which zone z0 belongs
     * param pageNum: the page on which zone z0 lives
     */
    contestednessVersus(hl, pageNum) {
        const A0 = this.area();
        return Array.from(this.highlights).reduce((acc, curr) => {
            if (curr === hl) {
                return acc;
            } else {
                return acc + A0/curr.zoneArea(pageNum);
            }
        }, 0);
    }

    buildDiv() {
        const div = document.createElement('div');
        div.classList.add('hl-region');
        div.style.left = this.x + 'px';
        div.style.width = (this.X - this.x) + 'px';
        div.style.top = this.y + 'px';
        div.style.height = (this.Y - this.y) + 'px';
        this.activateIfShared(div);
        return div;
    }

    isShared() {
        return this.highlights.size > 1;
    }

    isClaimed() {
        return this.claimedBy !== null;
    }

    claim(hl) {
        this.claimedBy = hl;
    }

    // If this region is shared -- meaning it belongs to more than one
    // highlight -- then it needs to define its own pointer event handlers.
    // Call this method to check if shared, and define handlers accordingly.
    activateIfShared(div) {
        if (this.isShared()) {
            if (this.isClaimed()) {
                const soleTarget = this.claimedBy;
                for (const eventName in ['click', 'mouseover', 'mouseout']) {
                    div.addEventListener(eventName, event => {
                        soleTarget.dispatchEvent(event);
                        event.stopPropagation();
                    });
                }
            } else {
                const hlArray = Array.from(this.highlights);
                div.classList.add('hl-intersection-region')
                div.addEventListener('click', event => {
                    // Only purpose here is to stop the click from reaching
                    // the enclosing hl-zone.
                    event.stopPropagation();
                });
                div.addEventListener('mouseover', event => {
                    for (let i = 0; i < hlArray.length; i++) {
                        const hl = hlArray[i];
                        hl.setTempColor(true, i % 4);
                    }
                    event.stopPropagation();
                });
                div.addEventListener('mouseout', event => {
                    for (let i = 0; i < hlArray.length; i++) {
                        const hl = hlArray[i];
                        hl.setTempColor(false, i % 4);
                    }
                    event.stopPropagation();
                });
            }
        }
    }
    
    // Compute the Venn diagram for this region and another.
    // returns: obj of the form {
    //   first: array of regions belonging only to this one
    //   both: the region that belonged to both, or null if
    //      they didn't intersect
    //   second: array of regions belonging only to the other
    // }
    venn(other) {
        const {x, X, y, Y} = this;
        const o = other;
        const [u, U, v, V] = [o.x, o.X, o.y, o.Y];
        const diag = {
            first: [],
            both: null,
            second: [],
        };
        // Note: We only care about interior intersections; if regions
        // intersect only along their boundaries, we ignore it.
        // Another way to say this is that we only want to produce
        // regions with non-zero width and height.
        // Therefore everywhere below we deliberately consider only cases
        // of strict inequalities, like u < X or v < y. 
        if (u < X && x < U && v < Y && y < V) {
            // The regions do intersect.
            //
            // Note: Our intended application area is highlight boxes in
            // text documents. It will be quite common for such boxes to span the
            // entire width of the document. Therefore, the y-dimension is our
            // best separator, meaning that, when a new box is introduced, it will
            // tend to be disjoint from most of the existing boxes in the y-dimension,
            // but not in the x-dimension.
            //
            // In light of this, where there are choices to be made in computing the
            // Venn diagram, we choose to make wide, flat regions, instead of tall, thin
            // regions.
            
            // Does one box start earlier in the y-dimension? If so, we have a new
            // region for that one's entire width, and for the y-interval up until
            // the second box begins.
            // If I begin before you...
            if (y < v) {
                // ...there's a region in my group, for my whole width, from where I
                // begin until where you begin.
                diag.first.push(new Region(x, X, y, v, this.highlights));
            } else if (v < y) {
                diag.second.push(new Region(u, U, v, y, other.highlights));
            }
            
            // Does one box *end* earlier in the y-dimension? If so, then we have a
            // new region for the *other* one's entire width, etc.
            // If I end before you...
            if (Y < V) {
                // ...there's a region in your group, for your whole width, from where
                // I end until where you end.
                diag.second.push(new Region(u, U, Y, V, other.highlights));
            } else if (V < Y) {
                diag.first.push(new Region(x, X, V, Y, this.highlights));
            }
            
            // Let [s, S] be the y-interval defined by the greatest lower bound and
            // least upper bound.
            const s = Math.max(y, v);
            const S = Math.min(Y, V);
            
            // Now we split up the y-interval [s, S] into potentially three regions
            // in the x-dimension (and at least one, namely, the two boxes' intersection).
            
            // Does one box start earlier in the x-dimension?
            if (x < u) {
                diag.first.push(new Region(x, u, s, S, this.highlights));
            } else if (u < x) {
                diag.second.push(new Region(u, x, s, S, other.highlights));
            }
            
            // Does one box end earlier in the x-dimension?
            if (X < U) {
                diag.second.push(new Region(X, U, s, S, other.highlights));
            } else if (U < X) {
                diag.first.push(new Region(U, X, s, S, this.highlights));
            }
            
            // The intersection:
            const r = Math.max(x, u);
            const R = Math.min(X, U);
            const combinedHls = new Set(
                Array.from(this.highlights).concat(Array.from(other.highlights))
            );
            diag.both = new Region(r, R, s, S, combinedHls);
            
        } else {
            diag.first.push(this);
            diag.second.push(other);
        }
        return diag;
    }
    
}


export class PageOfHighlights {
    
    constructor(documentController, pageNum, pageWidth) {
        this.documentController = documentController;
        this.pageNum = pageNum;
        this.pageWidth = pageWidth;

        // We store highlights and their regions by depth (i.e. "z-index") because
        // those belonging to different depths do not interact in any way. We compute
        // a separate Venn diagram for each depth. Finally, highlight divs are flowed
        // into the page's highlight layer in order of increasing depth, so that higher
        // elements are stacked on top of lower ones.
        this.highlightsByDepth = new Map();
        this.regionsByDepth = new Map();
    }

    addHighlights(hls) {
        for (const hl of hls) {
            this.addHighlight(hl);
        }
    }
    
    addHighlight(hl) {
        const depth = hl.depthsByPageNum.get(this.pageNum);
        const newRegions = hl.buildInitialRegionsForRenderedPage(this.pageNum, this.pageWidth);
        if (newRegions.length) {
            if (!this.highlightsByDepth.has(depth)) {
                this.highlightsByDepth.set(depth, []);
            }
            this.highlightsByDepth.get(depth).push(hl);

            // Have to add the new regions one at a time, because we can't assume
            // the boxes making up a Highlight start out disjoint. (Usually they
            // won't, since boxes representing adjacent rows of text tend to
            // have a little overlap.)
            let regions = this.regionsByDepth.get(depth) || [];
            for (let reg of newRegions) {
                regions = refine(regions, [reg]);
            }
            this.regionsByDepth.set(depth, regions);
        }
    }

    populateHighlightLayer(hlLayer) {
        hlLayer.addEventListener('click', event => {
            this.documentController.clearNamedHighlight();
        });

        // A page can be re-rendered (e.g. at a different zoom, or just after
        // scrolling away and back again), but Highlight instances can persist
        // across such renderings. So we have to start by clearing any existing
        // regions each Highlight may have already recorded for this page.
        this.clearExistingGraphicalElements();

        this.setRefinedRegionsIntoHighlights();
        this.resolveCompletelySharedZones();
        this.buildZoneDivs(hlLayer);
    }

    clearExistingGraphicalElements() {
        for (const hls of this.highlightsByDepth.values()) {
            for (const hl of hls) {
                hl.clearGraphicalElementsForPage(this.pageNum);
            }
        }
    }

    setRefinedRegionsIntoHighlights() {
        for (const regions of this.regionsByDepth.values()) {
            for (const region of regions) {
                for (const hl of region.highlights) {
                    hl.addRefinedRegionForPage(region, this.pageNum);
                }
            }
        }
    }

    /* Heuristic attempt to assign each "completely-shared" zone one region to be unshared,
     * and to forward mouse events to it, and to thereby make that zone accessible.
     *
     * A common case in which this is important is when one highlight is nested completely
     * inside another, e.g. a highlighted word or phrase within a whole highlighted paragraph.
     *
     * This is only a heuristic method, and there can be cases in which we are unable to
     * assign every zone a region. In such cases, the module author should utilize the `z`
     * command in the combiner code language to manually separate highlights into layers.
     */
    resolveCompletelySharedZones() {
        const p = this.pageNum;
        for (const hls of this.highlightsByDepth.values()) {
            const csZones = hls.filter(hl => hl.zoneIsCompletelyShared(p));
            // Future work:
            //  For now, we're just doing one initial sort, making one pass through the
            //  array, and hoping for the best.
            //  It might be better if we put the zones into a heap, and use heap sort to keep it
            //  sorted as we go. Would then "repair" the heap after each assignment, since making
            //  an assignment can change the ordering (by changing "flexibility" and "impact"
            //  ratings of each remaining zone).
            const triples = csZones.map(hl => [hl, hl.zoneRegionCount(p), hl.zoneImpact(p)]);
            triples.sort(compareCompletelySharedZones);
            for (const [hl, _, __] of triples) {
                // Try to assign a "least-contested" region that's still unassigned.
                hl.claimASharedRegion(p);
            }
        }
    }

    buildZoneDivs(hlLayer) {
        const depths = Array.from(this.highlightsByDepth.keys()).sort();
        for (const depth of depths) {
            const hls = this.highlightsByDepth.get(depth);
            for (const hl of hls) {
                const zoneDiv = hl.buildZoneDiv(this.pageNum);
                hlLayer.appendChild(zoneDiv);
            }
        }
    }
    
}


/* Given two arrays of regions, each of which is internally
 * pairwise disjoint, i.e. two Venn diagrams, combine them
 * into a single Venn diagram.
 */
function refine(existingRegions, newRegions) {
    const newTiling = [];
    
    while (existingRegions.length > 0) {
        const e = existingRegions.shift();
        let disjoint = true;
        for (let i = 0; i < newRegions.length; i++) {
            const n = newRegions[i];
            const venn = e.venn(n);
            if (venn.both !== null) {
                newTiling.push(venn.both);
                existingRegions.push(...venn.first);
                newRegions.splice(i, 1, ...venn.second);
                disjoint = false;
                break;
            }
        }
        if (disjoint) {
            newTiling.push(e);
        }
    }
    
    newTiling.push(...newRegions);
    
    return newTiling;
}


/* Comparison function for use when resolving "completely-shared" highlight zones,
 * i.e. trying to assign one shared region to each such zone.
 *
 * The idea is that we want to make assignments first for the zones that are
 * what we call "least flexible" (primarily) and "least impactful" (secondarily).
 * For each such zone, we want to choose a "least contested" region.
 *
 * contestedness of a region r, relative to a given zone z0 (could also be called the harmfulness
 * of assigning region r to zone z0): area of region r times sum of reciprocals of areas of its
 * zones *other than* z0.
 *
 *    Explanation: if zone z participates in region r, then area(r)/area(z) is a good
 *    measure of how badly z wants to claim r. The sum of these, over all zones z participating
 *    in the region r, other than the given zone z0, is a good measure of how much harm we'd
 *    do to the others by assigning r to z0.
 *
 *    A "good" contestedness score for a region can be expected to lie between 0 and 1 in
 *    common cases, such as when z0 has only one competitor z1, and z1 is large,
 *    relative to their intersection. This is the case e.g. when z1 covers a
 *    whole paragraph, while z0 is a small word or phrase contained therein.
 *
 * flexibility of a zone: its total number of regions.
 *
 *    Explanation: We want to handle the least flexible zones first, because assigning
 *    them a region is the most urgent. In particular, when flex(z) == 1, then zone z
 *    has only one possible assignment, so there's no choice to be made (except the order
 *    in which we make these assignments, which is why we measure "impact" -- see below).
 *
 * impact of a zone z0: sum of logs of contestedness of its regions.
 *
 *    Explanation: We want to measure how likely assigning zone z0 a region is
 *    to do harm to other zones. Therefore we want to reward zone z0 for having multiple
 *    "good" regions to choose from, which, as we've argued above, can often be expected
 *    to have contestedness scores between 0 and 1. Therefore taking the product of those scores
 *    should roughly achieve what we want. However, we don't want to worry about insufficient
 *    floating-point precision, so instead of multiplying, we sum logs.
 *
 * param a: triple [h, F, I], where h is a Highlight instance, F is the flexibility of
 *   h for the page in question, and I its impact for that page.
 * param b: triple [h, F, I] like a, to be compared to a
 *
 * return: negative, zero, or positive number, as required by a sorting comparison function
 */
function compareCompletelySharedZones(a, b) {
    const [aHl, aFlex, aImp] = a;
    const [bHl, bFlex, bImp] = b;
    // Sort primarily by ascending flexibility.
    const dF = aFlex - bFlex;
    if (dF !== 0) {
        return dF;
    }
    // Given same flexibility, sort by ascending impact.
    const dI = aImp - bImp;
    if (dI !== 0) {
        return dI;
    }
    // If impact also the same, finally sort by lex order on
    // highlightId, for determinism.
    const aName = aHl.highlightId;
    const bName = bHl.highlightId;
    return aName < bName ? -1 : (bName < aName ? 1 : 0);
}
