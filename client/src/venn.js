
// A component of a highlight
class Box {
    
    constructor(pageNum, x, X, y, Y) {
        this.pageNum = pageNum;
        this.x = x;
        this.X = X;
        this.y = y;
        this.Y = Y;
        this.highlight = null;
    }
    
    asRegion() {
        return new Region(this.x, this.X, this.y, this.Y, [this]);
    }
    
}


// A collection of boxes, potentially spanning multiple pages.
class Highlight {
    
    constructor(boxes) {
        boxes = boxes || [];
        this.boxes = [];
        for (let box of boxes) {
            this.addBox(box);
        }
    }
    
    addBox(box) {
        this.boxes.push(box);
        box.highlight = this;
    }
    
}


// A single Venn diagram region, among all the boxes on a single page.
class Region {
    
    /* x: min x coord
     * X: max X coord
     * y: min y coord
     * Y: max y coord
     * boxes: array of Box instances to which this region belongs
     */
    constructor(x, X, y, Y, boxes) {
        this.x = x;
        this.X = X;
        this.y = y;
        this.Y = Y;
        this.boxes = boxes || [];
    }
    
    addBox(box) {
        this.boxes.push(box);
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
                diag.first.push(new Region(x, X, y, v, this.boxes));
            } else if (v < y) {
                diag.second.push(new Region(u, U, v, y, other.boxes));
            }
            
            // Does one box *end* earlier in the y-dimension? If so, then we have a
            // new region for the *other* one's entire width, etc.
            // If I end before you...
            if (Y < V) {
                // ...there's a region in your group, for your whole width, from where
                // I end until where you end.
                diag.second.push(new Region(u, U, Y, V, other.boxes));
            } else if (V < Y) {
                diag.first.push(new Region(x, X, V, Y, this.boxes));
            }
            
            // Let [s, S] be the y-interval defined by the greatest lower bound and
            // least upper bound.
            const s = Math.max(y, v);
            const S = Math.min(Y, V);
            
            // Now we split up the y-interval [s, S] into potentially three regions
            // in the x-dimension (and at least one, namely, the two boxes' intersection).
            
            // Does one box start earlier in the x-dimension?
            if (x < u) {
                diag.first.push(new Region(x, u, s, S, this.boxes));
            } else if (u < x) {
                diag.second.push(new Region(u, x, s, S, other.boxes));
            }
            
            // Does one box end earlier in the x-dimension?
            if (X < U) {
                diag.second.push(new Region(X, U, s, S, other.boxes));
            } else if (U < X) {
                diag.first.push(new Region(U, X, s, S, this.boxes));
            }
            
            // The intersection:
            const r = Math.max(x, u);
            const R = Math.min(X, U);
            diag.both = new Region(r, R, s, S, this.boxes.concat(other.boxes));
            
            
        } else {
            diag.first.push(this);
            diag.second.push(other);
        }
        return diag;
    }
    
}


class Page {
    
    constructor(pageNum) {
        this.pageNum = pageNum;
        this.highlights = [];
        this.regions = [];
    }
    
    addHighlight(hl) {
        const presentBoxes = hl.boxes.filter(b => b.pageNum === this.pageNum);
        if (presentBoxes.length) {
            this.highlights.push(hl);
            const newRegions = presentBoxes.map(b => b.asRegion());
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





function test01() {
    let B1 = new Box(11, 0, 100, 7, 19);
    let B2 = new Box(11, 0, 33, 17, 27);
    let hl1 = new Highlight([B1, B2]);

    let B3 = new Box(11, 20, 40, 15, 25);
    let B4 = new Box(12, 0, 100, 56, 67);
    let hl2 = new Highlight([B3, B4]);

    let pg11 = new Page(11);
    pg11.addHighlight(hl1);
    pg11.addHighlight(hl2);

}


test01();










