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

const ise = {};

define([
    "ise/content_types/pdf/pdf_util",
], function(
    pdf_util,
) {
    ise.pdf_util = pdf_util;
});


// A collection of boxes, potentially spanning multiple pages.
export class Highlight {
    
    constructor(documentController, highlightDescriptor) {
        this.documentController = documentController;
        this.highlightDescriptor = highlightDescriptor;
        this.selectionBoxesByPageNum = new Map();
        this.refinedRegionsByPageNum = new Map();
        this.zoneDivsByPageNum = new Map();

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
    }

    // List the page numbers on which this highlight has presence.
    listPageNums() {
        return Array.from(this.selectionBoxesByPageNum.keys());
    }

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

    clearRefinedRegionsForPage(pageNum) {
        this.refinedRegionsByPageNum.set(pageNum, []);
    }

    // After all highlights for a page have been combined and their regions
    // refined, this method can be used to tell this highlight about the refined regions.
    addRefinedRegionForPage(region, pageNum) {
        this.refinedRegionsByPageNum.get(pageNum).push(region);
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
    }

    scrollIntoView() {
        const firstZone = this.zoneDivsByPageNum.get(this.firstPage());
        const firstRegion = firstZone.querySelector('.hl-region');
        this.documentController.scrollIntoView(firstRegion);
    }

    buildZoneDiv(pageNum) {
        const div = document.createElement('div');
        div.classList.add('hl-zone');
        for (const region of this.refinedRegionsByPageNum.get(pageNum) || []) {
            div.appendChild(region.buildDiv());
        }
        div.addEventListener('mouseover', event => {
            this.setTempColor(true, 0);
            this.documentController.broadcastHighlightMouseEvent(
                event, this.highlightDescriptor
            );
        });
        div.addEventListener('mouseout', event => {
            this.setTempColor(false, 0);
            this.documentController.broadcastHighlightMouseEvent(
                event, this.highlightDescriptor
            );
        });
        div.addEventListener('click', event => {
            this.documentController.clearNamedHighlight();
            this.clearAllTempColors();
            this.select(true);
            event.stopPropagation();
            this.documentController.broadcastHighlightMouseEvent(
                event, this.highlightDescriptor
            );
        });
        this.zoneDivsByPageNum.set(pageNum, div);
        return div;
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
    }

    buildDiv() {
        const div = document.createElement('div');
        div.classList.add('hl-region');
        div.style.left = this.x + 'px';
        div.style.width = (this.X - this.x) + 'px';
        div.style.top = this.y + 'px';
        div.style.height = (this.Y - this.y) + 'px';
        this.activateIfMulti(div);
        return div;
    }

    // If this region "is multi" -- meaning it belongs to more than one
    // highlight -- then it needs to define its own pointer event handlers.
    // Call this method to check if multi, and define handlers iff so.
    activateIfMulti(div) {
        const hlArray = Array.from(this.highlights);
        if (hlArray.length > 1) {
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
        this.highlights = [];
        this.regions = [];
    }

    addHighlights(hls) {
        for (const hl of hls) {
            this.addHighlight(hl);
        }
    }
    
    addHighlight(hl) {
        const newRegions = hl.buildInitialRegionsForRenderedPage(this.pageNum, this.pageWidth);
        if (newRegions.length) {
            this.highlights.push(hl);
            // Have to add the new regions one at a time, because we can't assume
            // the boxes making up a Highlight start out disjoint. (Usually they
            // won't, since boxes representing adjacent rows of text tend to
            // have a little overlap.)
            let regions = this.regions;
            for (let reg of newRegions) {
                regions = refine(regions, [reg]);
            }
            this.regions = regions;
        }
    }

    populateHighlightLayer(hlLayer) {
        hlLayer.addEventListener('click', event => {
            this.documentController.clearNamedHighlight();
        });
        this.setRefinedRegionsIntoHighlights();
        this.buildZoneDivs(hlLayer);
    }

    setRefinedRegionsIntoHighlights() {
        // A page can be re-rendered (e.g. at a different zoom, or just after
        // scrolling away and back again). But Highlight instances can persist
        // across such renderings. So we have to start by clearing any existing
        // regions each Highlight may have already recorded for this page.
        for (const hl of this.highlights) {
            hl.clearRefinedRegionsForPage(this.pageNum);
        }
        for (const region of this.regions) {
            for (const hl of region.highlights) {
                hl.addRefinedRegionForPage(region, this.pageNum);
            }
        }
    }

    buildZoneDivs(hlLayer) {
        for (const hl of this.highlights) {
            const zoneDiv = hl.buildZoneDiv(this.pageNum);
            hlLayer.appendChild(zoneDiv);
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
