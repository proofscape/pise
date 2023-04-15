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

define([
    "dojo/_base/declare"
], function(
    declare
){
var pdf_util = {};

pdf_util.SelectionBox = function() {
    this.W = null;
    this.H = null;
    this.x = null;
    this.y = null;
    this.w = null;
    this.h = null;
    this.pageNumber = null;
    this.canvas = null;
    this.imgData = null;
    this.captureBox = null;
};

pdf_util.SelectionBox.prototype = {

    writeDescription: function() {
        return [this.pageNumber, this.W, this.H, this.x, this.y, this.w, this.h].join(":");
    },

    round: function() {
        this.W = Math.round(this.W);
        this.H = Math.round(this.H);
        this.x = Math.round(this.x);
        this.y = Math.round(this.y);
        this.w = Math.round(this.w);
        this.h = Math.round(this.h);
    },

    makeScaledCopy: function(s) {
        var copy = new pdf_util.SelectionBox();
        copy.W = s*this.W;
        copy.H = s*this.H;
        copy.x = s*this.x;
        copy.y = s*this.y;
        copy.w = s*this.w;
        copy.h = s*this.h;
        copy.pageNumber = this.pageNumber;
        copy.canvas = this.canvas;
        return copy;
    },

    makeRoundedScaledCopy: function(s) {
        var copy = this.makeScaledCopy(s);
        copy.round();
        return copy;
    },

    /* Capture image data from a canvas, producing a new SelectionBox instance.
     * The new box will be scaled to match the canvas size, and will contain image data.
     * It will also be stored in this box, as `this.captureBox`.
     *
     * param canvas: the canvas from which to capture. If defined, set as this.canvas.
     *   If undefined, try to use this.canvas.
     * return: the new box.
     */
    captureFromCanvas: function(canvas) {
        canvas = canvas || this.canvas;
        if (canvas === undefined) throw new Error('no canvas');
        this.canvas = canvas;
        var ctx = canvas.getContext("2d");
        var s = canvas.width / this.W;
        var box = this.makeScaledCopy(s);
        box.round();
        box.imgData = ctx.getImageData(box.x, box.y, box.w, box.h);
        this.captureBox = box;
        // Since the new box has image data, it is regarded as its own capture box:
        box.captureBox = box;
        return box;
    },

};

pdf_util.getCanvasDisplayScale = function(canvas) {
    return canvas.width/canvas.clientWidth;
};

/* Make a new SelectionBox instace based on a selection rectangle from the box
 * layer of a rendered PDF page, in the generic viewer.
 *
 * This factory function sets more properties in the SelectionBox than that
 * class's constructor specifies, just in case they are useful.
 */
pdf_util.makeSelectionBoxFromDomNode = function(domNode) {
    var selbox = new pdf_util.SelectionBox();
    selbox.W = domNode.parentNode.clientWidth;
    selbox.H = domNode.parentNode.clientHeight;
    selbox.x = domNode.offsetLeft;
    selbox.y = domNode.offsetTop;

    // Here we do want to use offset width and height (not client w & h), since
    // the user will expect the border to be included. Otherwise if the selection
    // box is drawn very tightly, you can unexpectedly shave a pixel off the edges
    // of what you wanted to select.
    selbox.w = domNode.offsetWidth;
    selbox.h = domNode.offsetHeight;

    selbox.domNode = domNode;
    selbox.parentNode = domNode.parentNode;
    selbox.page = selbox.parentNode.parentNode;
    selbox.pageNumber = +selbox.page.getAttribute('data-page-number');
    selbox.pageLabel = selbox.page.getAttribute('data-page-label');
    selbox.canvas = selbox.page.querySelector('canvas');
    // good for experiments: grab a different, fixed canvas instead...
    //selbox.canvas = selbox.page.parentNode.querySelector('#page211');
    return selbox;
};

/* Make a new SelectionBox instance based on a description of the kind returned
 * by SelectionBox.writeDescription().
 */
pdf_util.makeSelectionBoxFromDescrip = function(descrip) {
    var selbox = new pdf_util.SelectionBox();
    var parts = descrip.split(":");
    selbox.pageNumber = +parts[0],
    selbox.W = +parts[1],
    selbox.H = +parts[2],
    selbox.x = +parts[3],
    selbox.y = +parts[4],
    selbox.w = +parts[5],
    selbox.h = +parts[6];
    return selbox;
};


/* Render a combiner program on a canvas.
 *
 * param prog: a CombinerProgram
 * param canvas: the canvas element where rendering should take place
 * param displayScaling: optional scaling factor for the display of the canvas.
 *   If defined, the canvas's CSS width and height will be set to be its
 *   actual width and height times this factor.
 * return: the dimensions of the bounding box of the final drawing
 */
pdf_util.renderProgram = function(prog, canvas, displayScaling) {
    var ctx = canvas.getContext('2d');
    // First do a dry run just to compute dimensions.
    var dims = prog.execute(null);
    // Now set the dimensions, clear the canvas, and do a run with actual rendering.
    canvas.width = dims.w;
    canvas.height = dims.h;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (displayScaling !== undefined) {
        var ds = displayScaling;
        canvas.style.width = Math.round(dims.w * ds)+'px';
        canvas.style.height = Math.round(dims.h * ds)+'px';
    }
    return prog.execute(ctx);
};

pdf_util.CombinerCmd = declare(null, {
    type: null,
    rawCode: null,
    constructor: function(code) {
        this.rawCode = code;
    },
    scale: function(s) {},
    str: function() {
        return this.rawCode;
    },
    /* Execute the command.
     * param pos: object w/ properties x and y, giving current position
     * param size: object w/ properties w and h, giving the current size of the
     *   bounding box
     * param ctx: a canvas 2d context; pass null for a dry run, which will compute
     *   the size but will not write anything into the canvas context.
     */
    execute: function(pos, size, ctx) {},
});

pdf_util.CombinerCmdScale = declare(pdf_util.CombinerCmd, {
    type: 'scale',
    scale: null,
    constructor: function(code) {
        this.scale = +code.slice(1);
    },
});

/* Depth command format:
 *  'z' followed by one or more integers, separated by commas.
 *  Integers may have sign, or not.
 *
 *  If a single integer is given, this is taken as the depth for all
 *  pages. Otherwise, you should list one integer for every page on which
 *  boxes are found in this program.
 */
pdf_util.CombinerCmdDepth = declare(pdf_util.CombinerCmd, {
    type: 'depth',
    depths: null,
    constructor: function(code) {
        this.depths = code.slice(1).split(',').map(n => +n);
    },
});

pdf_util.CombinerCmdBox = declare(pdf_util.CombinerCmd, {
    type: 'box',
    boxDescrip: null,
    selBox: null,
    captureBox: null,
    nominalWidth: null,  // see `scale` method
    nominalHeight: null,
    // Along with the code, pass a lookup in which the box description points
    // to the SelectionBox itself.
    constructor: function(code, boxLookup) {
        this.boxDescrip = code.slice(1, -1);
        // If you haven't even passed a box lookup, we presume you don't care
        // about boxes, so we stop here.
        if (!boxLookup) return;
        // Otherwise we presume you do care about boxes, so it's an error if
        // we can't find the one for this command.
        this.selBox = boxLookup[this.boxDescrip];
        if (!this.selBox) throw new Error('Box not found: ' + this.boxDescrip);
        this.captureBox = this.selBox.captureBox;
        // Read dimensions off capture box if it's defined; else off selection box.
        var dimsBox = this.captureBox || this.selBox;
        this.nominalWidth = dimsBox.w;
        this.nominalHeight = dimsBox.h;
    },
    /* Note: it is due to the partial and incomplete character of this scaling
     * operation that this class stores properties called "nominal" width and
     * height. The point is: those properties are going to be scaled, _but the
     * actual image data for this box is not_. The whole purpose of this scaling
     * operation is just so that this box command can be useful in computing the
     * _size_ of a box combination at a planned scale.
     *
     * Note2: We're no longer actually using this method anyway. But we'll keep it
     * around for now.
     */
    scale: function(s) {
        this.nominalWidth = Math.round(s*this.nominalWidth);
        this.nominalHeight = Math.round(s*this.nominalHeight);
    },
    // The "rendering zoom" refers to the blow-up factor from the size of the
    // selection box to the size of its capture box.
    getRenderingZoom: function() {
        var B = this.selBox,
            C = this.captureBox;
        // If we don't have a capture box, it means we're trying to render a
        // blank canvas, so we just want rendering zoom of unity.
        if (C === null) return 1;
        return C.W/B.W;
    },
    execute: function(pos, size, ctx) {
        if (ctx !== null && this.captureBox !== null) {
            var imgData = this.captureBox.imgData;
            if (imgData) ctx.putImageData(imgData, pos.x, pos.y);
        }
        pos.x += this.nominalWidth;
        size.w = Math.max(size.w, pos.x);
        size.h = Math.max(size.h, pos.y + this.nominalHeight);
    },
});

pdf_util.CombinerCmdShift = declare(pdf_util.CombinerCmd, {
    type: 'shift',
    dim: null,
    pixels: null,
    sign: null,
    unit: null,
    constructor: function(code) {
        this.dim = code[0];
        this.pixels = +code.slice(2);
        this.sign = code[1];
        this.unit = this.sign === '-' ? -1 : 1;
    },
    scale: function(s) {
        this.pixels = (this.pixels * s).toFixed(3);
    },
    str: function() {
        return this.dim + this.sign + this.pixels;
    },
    execute: function(pos, size, ctx) {
        if (isNaN(this.pixels)) return;
        pos[this.dim] += this.unit * this.pixels;
    },
});

pdf_util.CombinerCmdNewline = declare(pdf_util.CombinerCmd, {
    type: 'newline',
    execute: function(pos, size, ctx) {
        pos.x = 0;
        pos.y = size.h;
    },
});

/* Parse a string of combiner code v2
 *
 * param code: the code to be parsed
 * param selBoxesByDescrip: lookup of SelectionBoxes by their descriptions
 * return: a CombinerProgram instance
 */
pdf_util.parseCombinerCode = function(code, selBoxesByDescrip) {
    const cmds = [];
    const codeStrings = code.split(';').map(s => s.trim());
    // Check that it's v2 before processing.
    if (codeStrings.length > 0 && codeStrings[0] === 'v2') {
        codeStrings.shift();
        codeStrings.forEach(code => {
            var c0 = code[0];
            var cmd = null;
            switch (c0) {
                case 's':
                    cmd = new pdf_util.CombinerCmdScale(code);
                    break;
                case 'z':
                    cmd = new pdf_util.CombinerCmdDepth(code);
                    break;
                case "(":
                    cmd = new pdf_util.CombinerCmdBox(code, selBoxesByDescrip);
                    break;
                case 'x':
                    cmd = new pdf_util.CombinerCmdShift(code);
                    break;
                case 'y':
                    cmd = new pdf_util.CombinerCmdShift(code);
                    break;
                case 'n':
                    cmd = new pdf_util.CombinerCmdNewline(code);
                    break;
            }
            if (cmd !== null) cmds.push(cmd);
        });
    }
    return new pdf_util.CombinerProgram(cmds);
};

pdf_util.CombinerProgram = declare(null, {
    cmds: null,
    scale: 1,
    depths: [0],
    // cmds: array of CombinerCmd instances
    constructor: function(cmds) {
        this.cmds = cmds;
        this.readScale();
        this.readDepths();
    },
    // Set this program's scale based on the (last) scale command.
    readScale: function() {
        var prog = this;
        this.cmds.forEach(cmd => {
            if (cmd.type === 'scale') prog.scale = cmd.scale;
        });
    },
    // Set this program's depth(s) based on the (last) depth command.
    readDepths: function() {
        this.cmds.forEach(cmd => {
            if (cmd.type === 'depth') this.depths = cmd.depths;
        });
    },
    // Read the rendering zoom off the first box command. We presume that,
    // within a single program, all boxes will wind up with the same rendering
    // zoom, so no problem just reading it off the first one.
    getRenderingZoom: function() {
        for (var i in this.cmds) {
            var cmd = this.cmds[i];
            if (cmd.type === 'box') {
                return cmd.getRenderingZoom();
            }
        }
        throw new Error('program has no boxes');
    },
    getBoxDescrips: function() {
        var descrips = [];
        this.cmds.forEach(cmd => {
            if (cmd.type === 'box') descrips.push(cmd.boxDescrip);
        });
        return descrips;
    },
    /* Execute the program.
     * param ctx: a canvas 2d context; pass null for a dry run, which will compute
     *   the size but will not write anything into the canvas context.
     * return: the final size of the bounding box
     */
    execute: function(ctx) {
        var pos = {x:0, y:0}, size = {w:0, h:0};
        this.cmds.forEach(cmd => {
            cmd.execute(pos, size, ctx);
        });
        return size;
    },
    // Scale each command by a given factor.
    scale: function(s) {
        this.cmds.forEach(cmd => {
            cmd.scale(s);
        });
    },
    // Scale just the shift commands by a given factor.
    scaleShifts: function(s) {
        this.cmds.forEach(cmd => {
            if (cmd.type === 'shift') cmd.scale(s);
        });
    },
    // Write a string representation of the program.
    // Pass a truthy value to write in multiline format; else written in a single line.
    write: function(multiline) {
        var j = multiline ? ';\n' : ';';
        return this.cmds.map(c => c.str()).join(j);
    },
});

/* Given an array of combiner code strings, make a SelectionBox for
 * every box command in every code string, and return the array of all these,
 * in the order encountered.
 *
 * param codes: array of combiner code strings
 * return: array of SelectionBoxes, being all those described in any of the
 *   given code strings
 */
pdf_util.makeAllBoxesFromCombinerCodes = function(codes) {
    var descrips = [];
    codes.forEach(code => {
        var prog = pdf_util.parseCombinerCode(code, null);
        descrips = descrips.concat(prog.getBoxDescrips());
    });
    var Bi = descrips.map(pdf_util.makeSelectionBoxFromDescrip);
    return Bi;
};

/* Given an array of SelectionBoxes, return an array in which each
 * entry is of the form,
 *     {pageNum: int, boxes: array}
 * indicating a page number, and the array of all boxes that lie on
 * that page. The returned array is sorted by increasing page number.
 *
 * param boxes: array of SelectionBoxes
 * return: sorted array of the form [ {pageNum: int, boxes: array} ] (see above)
 */
pdf_util.sortBoxesByPageNumber = function(boxes) {
    var sorted = [];
    var groupByPageNumber = {};
    boxes.forEach(box => {
        var a = groupByPageNumber[box.pageNumber] || [];
        a.push(box);
        groupByPageNumber[box.pageNumber] = a;
    });
    var nums = Object.keys(groupByPageNumber).map(s => +s).sort((a, b) => a - b);
    var sorted = nums.map(n => {
        return {pageNum: n, boxes: groupByPageNumber[n]};
    });
    return sorted;
};

return pdf_util;
});
