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

import { moose } from "pfsc-moose/src/moose/head";

define([], function(){
var util = {};

/* Assign property values to a target object from alternative source objects.
 * The source objects are checked, in order, for a defined value of each
 * property. Once a defined value is found, it is accepted; if none is found
 * the property is left undefined in the target.
 *
 * param target: the target object
 * param props: array of property names that are to be assigned
 * param sources: array of source objects to be considered in order
 *
 * return: nothing; target is modified in-place
 */
util.assign = function(target, props, sources) {
    var N = sources.length;
    props.forEach(prop => {
        var i = 0;
        while (i < N) {
            var v = sources[i++][prop];
            if (typeof v !== 'undefined') {
                target[prop] = v;
                break;
            }
        }
    });
};

util.copyTextToClipboard = function(text) {
    var box = document.createElement("textarea");
    box.value = text;
    box.style.opacity = 0;
    document.body.appendChild(box);
    box.focus();
    box.select();
    document.execCommand('copy');
    box.remove();
};

/* Copy text to clipboard and flash a brief message at a given point.
 * The default message is "Copied!".
 *
 * param text: (str) the text to be copied to clipboard
 * param pt: [x, y] coords where message should be displayed
 * param message: (str) optional text of message. Default: "Copied!"
 */
util.copyTextWithMessageFlash = function(text, pt, message) {
    message = message || "Copied!";
    var x = pt[0],
        y = pt[1];
    util.copyTextToClipboard(text);
    // Display a brief notice saying "Copied!"
    var note = document.createElement('div');
    note.classList.add("briefNotice");
    note.innerHTML = "Copied!";
    // Place it at a slight offset from the mouse cursor.
    note.style.left = x + 'px';
    note.style.top = y + 'px';
    document.body.appendChild(note);
    // Wait a moment to initiate fade-out.
    setTimeout(function(){
        note.style.opacity = 0;
    }, 400);
    // After fade-out, remove the element.
    setTimeout(function(){
        note.remove();
    }, 1000);
};

/* Same as `copyTextWithMessageFlash` only the display point is automatically
 * set up based on a click event.
 */
util.copyTextWithMessageFlashAtClick = function(text, event, message) {
    var x = event.pageX + 8;
    var y = event.pageY + 8;
    util.copyTextWithMessageFlash(text, [x, y], message);
};

/* Display a notification box in a corner of the screen.
 *
 * param messageHtml: HTML to be displayed as message in the box.
 * param buttonText: string to appear on the "OK" button. Default "OK".
 * param cornerCode: string in ['ll', 'lr', 'tl', 'tr'] indicating where the box
 *   should appear. Default 'll'.
 * param additionalStyling: object where you may set additional CSS style key-value pairs,
 *   to be applied to the outer box. E.g. width may be set here if desired.
 * return: promise that resolves after user clicks the "OK" button.
 */
util.showCornerNoticeBox = function(messageHtml, buttonText, cornerCode, additionalStyling) {
    cornerCode = cornerCode || 'll';
    buttonText = buttonText || 'OK';
    additionalStyling = additionalStyling || {};

    const box = document.createElement('div');
    box.classList.add("noticeBox");

    const messageArea = document.createElement('div');
    messageArea.innerHTML = messageHtml;
    box.appendChild(messageArea);

    const offset = 24;
    switch (cornerCode) {
        case 'll':
            box.style.bottom = offset + 'px';
            box.style.left = offset + 'px';
            break;
        case 'lr':
            box.style.bottom = offset + 'px';
            box.style.right = offset + 'px';
            break;
        case 'tl':
            box.style.top = offset + 'px';
            box.style.left = offset + 'px';
            break;
        case 'tr':
            box.style.top = offset + 'px';
            box.style.right = offset + 'px';
            break;
    }

    Object.assign(box.style, additionalStyling);

    const buttonRow = document.createElement('div');
    buttonRow.classList.add('buttonRow');
    const button = document.createElement('button');
    button.innerText = buttonText;
    buttonRow.appendChild(button);
    box.appendChild(buttonRow);

    return new Promise(resolve => {
        button.addEventListener('click', evt => {
            box.remove();
            resolve();
        });
        document.body.appendChild(box);
    });
};

/* Add a "tail selector" to an element.
 *
 * Let W be an array of words (strings). Let P be the dot-delimited path
 * on these words. A subpath, starting from any word w in W, and going to
 * the right-hand end of P, is called a "tail". This function builds a widget
 * that allows the user to hover over any word, and thereby highlight the
 * tail that begins at that word; clicking then copies that tail to the clipboard.
 *
 * param home: the element to which the tail selector is to be added
 * param words: the array of words
 */
util.addTailSelector = function(home, words) {
    // Form a tailSelector span to hold the whole widget.
    const span = document.createElement('span');
    span.classList.add('tailSelector');
    // Must add the selector span to the given home now.
    // It has to be a part of the document, so that we can read the
    // sizes off of the individual word segments.
    home.appendChild(span);
    // Now we iterate over the words in reverse order, building
    // successively longer tails. For each tail, we form a highlight span.
    // We store these now, so that we can then add them to the selector
    // in the opposite order.
    const n = words.length;
    const hls = [];
    let tail = null;
    for (let i = 0; i < n; i++) {
        // Form the tail.
        tail = words.slice(n-1-i).join('.');
        // Form the highlight span.
        const hl = document.createElement('span');
        hl.classList.add("tailSelectorHighlight");
        hl.innerHTML = tail;
        // Push it into the front of the array of highlights.
        hls.unshift(hl);
        // Set the onclick handler for the highlight. We need to
        // do this within a closure, since we're in a for-loop.
        (function(hl, tail){
            // click handler:
            hl.addEventListener('click', function(event){
                util.copyTextWithMessageFlashAtClick(tail, event);
            });
        })(hl, tail);
    }
    // Before adding any of the highlight spans, first add a base span
    // to show the entire path.
    const baseSpan = document.createElement('span');
    baseSpan.innerHTML = tail;
    span.appendChild(baseSpan);
    // Now stack up the highlights, working from longest to shortest.
    for (let hl of hls) {
        span.appendChild(hl);
    }
};

/* Given the libpath of a top-level entity, return its modpath.
 *
 * All this does is reeturn the string resulting from chopping off
 * the final segment of the given libpath.
 */
util.getModpathFromTopLevelEntityPath = function(tlepath) {
    return tlepath.slice(0, tlepath.lastIndexOf('.'));
};

/* Given any libpath, return the repopath prefix.
 */
util.getRepoPart = moose.getRepoPart;


/* Given a libpath and version, return the URL at which this object can be
 * viewed at the remote host.
 *
 * @param libpath: the libpath of interest.
 * @param version: the version of interest.
 * @param isDir: set true if this libpath points to a module and
 *   you want the page for that module _as a directory_. Otherwise
 *   we make the URL for the given libpath _as a file_.
 * @param sourceRow: when `isDir` is false, you may pass a positive integer
 *   here, naming a row in the source file you want to select.
 * @param modIsTerm: when `isDir` is false, you may pass a boolean indicating
 *   whether the module in which this item lives is a terminal module.
 *
 * @return: URL string, or null if the given libpath does not
 *   point to a known remote host.
 */
util.libpath2remoteHostPageUrl = function(libpath, version, isDir, sourceRow, modIsTerm) {
    const lpParts = libpath.split('.');
    let host = lpParts[0];
    // For testing purposes (and doesn't hurt anything in production):
    if (libpath.startsWith('test.hist.')) {
        host = 'ex';
    }
    if (!['gh', 'bb', 'ex'].includes(host)) {
        return null;
    }
    let urlParts = [];
    urlParts.push({
        gh: 'https://github.com',
        bb: 'https://bitbucket.org',
        ex: 'https://example.org',
    }[host]);
    urlParts.push(lpParts[1]); // owner
    urlParts.push(lpParts[2]); // repo
    urlParts.push(host === 'bb' ? 'src' : isDir ? 'tree' : 'blob');
    urlParts.push(version === "WIP" ? 'main' : version);
    urlParts = urlParts.concat(lpParts.slice(3));
    if (!isDir) {
        let suffix = '.pfsc'
        if (sourceRow) {
            suffix += `#${host !== 'bb' ? "L" : "lines-"}${sourceRow}`;
        }
        if (modIsTerm) {
            urlParts[urlParts.length - 1] += suffix;
        } else {
            urlParts.push('__' + suffix);
        }
    } else if (host === 'bb') {
        // BitBucket likes directories to end with a '/'
        urlParts.push('');
    }
    return urlParts.join('/');
};

util.libpathIsRemote = function(libpath) {
    return libpath.startsWith('gh.') ||
           libpath.startsWith('bb.') ||
           // For testing purposes (and doesn't hurt anything in production):
           libpath.startsWith('test.hist.');
};

/* Given any libpath, return the libpath of the parent,
 * unless the given libpath is already a repopath, in which
 * case just return it unchanged.
 */
util.getParentPath = function(libpath) {
    let parts = libpath.split('.');
    if (parts.length > 3) {
        parts = parts.slice(0, -1);
    }
    return parts.join('.');
};

util.libpathIsPrefix = function(potential_prefix, other_libpath) {
    const n = potential_prefix.length;
    const front = other_libpath.slice(0, n);
    const back = other_libpath.slice(n);
    return front === potential_prefix && (back.length === 0 || back.startsWith('.'));
};

// Version tag regex:
util.vTagRe = new RegExp('^v(0|[1-9]\\d*)\\.(0|[1-9]\\d*)\\.(0|[1-9]\\d*)$');

/* Parse a widget UID, producing a libpath and version tag.
 *
 * The form of a widget UID is `widgetpath_version` with all dots replaced by hyphens.
 * Given a string of this form, we compute the libpath of the widget, and the version tag.
 */
util.parseWidgetUid = function(uid) {
    const i0 = uid.lastIndexOf("_");
    const hyphenatedLibpath = uid.slice(0, i0);
    const hyphenatedVersion = uid.slice(i0 + 1);
    const libpath = hyphenatedLibpath.replaceAll('-', '.');
    const version = hyphenatedVersion.replaceAll('-', '.');
    return {
        libpath: libpath,
        version: version,
    };
};

/* Parse a tail-versioned libpath. This means a libpath with a version
 * tag at the tail end, as in `libpath@version`.
 *
 * If no version is provided, we take this to mean WIP.
 *
 * @param tvlp: string, giving a tail-versioned libpath.
 * @param options: {
 *   defaultVersion: value to return for version if the given libpath
 *     does not define one. Defaults to "WIP".
 * }
 * @return: object with `libpath` and `version` properties, pointing to strings.
 */
util.parseTailVersionedLibpath = function(tvlp, options) {
    const {
        defaultVersion = "WIP",
    } = options || {};
    const parts = tvlp.split("@");
    const libpath = parts[0];
    let version;
    if (parts.length === 1) {
        version = defaultVersion;
    }
    else if (parts.length === 2) {
        version = parts[1];
        if (version !== "WIP") {
            // Validate version string with regex.
            if (!util.vTagRe.test(version)) {
                throw new Error("Malformed version tag: " + version);
            }
        }
    }
    else {
        throw new Error("Malformed tail-versioned libpath: " + tvlp);
    }
    return {
        libpath: libpath,
        version: version,
    };
};

util.lv = function(libpath, version) {
    return `${libpath}@${version}`;
}

util.pvl = util.parseTailVersionedLibpath;

/* Given a "tail-versioned repopath" (a repopath with an @dotted-version at
 * the end), and a "memberpath" (a libpath lying under said repopath),
 * return the result of attaching the underscore-version tag to the repo segment
 * of the memberpath.
 *
 * For example, given `some.great.repo@v3.1.4` and `some.great.repo.member.path`,
 * you will get `some.great.repo@v3_1_4.member.path`.
 */
util.applyTvrpToMemberpath = function(tvrp, memberpath) {
    const [repopath, dotted_version] = tvrp.split("@");
    const uscore_version = dotted_version.replaceAll('.', "_");
    const parts = memberpath.split('.');
    let remainder = parts.slice(3).join('.');
    if (remainder) remainder = '.' + remainder;
    return `${repopath}@${uscore_version}${remainder}`;
}

/* Remove everything from inside a DOM element.
 */
util.removeAllChildNodes = function(parent) {
    while (parent.firstChild) {
        parent.removeChild(parent.firstChild);
    }
}

/* A "set-mapping" is a Map whose values are Sets.
 */
class SetMapping {

    constructor() {
        this.mapping = new Map();
    }

    /* Add a value to the set for a given key.
     * If the key is new, make it map to the singleton set on the given value.
     */
    add(key, value) {
        if (this.mapping.has(key)) {
            this.mapping.get(key).add(value);
        } else {
            this.mapping.set(key, new Set([value]));
        }
    }

    /* Remove a value from the set for a given key.
     * If the key or value is not present, do nothing.
     * If the key is present, and the value is the last element in the set
     *   for that key, remove the key from the mapping.
     */
    remove(key, value) {
        if (this.mapping.has(key)) {
            const set = this.mapping.get(key);
            set.delete(value);
            if (set.size === 0) {
                this.mapping.delete(key);
            }
        }
    }

    /* Say whether we have a given value in the set under a given key.
     */
    has(key, value) {
        return this.mapping.has(key) && this.mapping.get(key).has(value);
    }
}

util.SetMapping = SetMapping;

class LibpathSetMapping extends SetMapping {

    constructor() {
        super();
    }

    /* Find all keys that are equal to or proper extensions of a given
     * libpath prefix, and return the union of their values.
     */
    getUnionOverLibpathPrefix(prefix) {
        const union = new Set();
        for (let [key, value] of this.mapping) {
            if (util.libpathIsPrefix(prefix, key)) {
                for (let elem of value) {
                    union.add(elem);
                }
            }
        }
        return union;
    }
}

util.LibpathSetMapping = LibpathSetMapping;

util.setUnion = function(p, q) {
    const r = new Set(p)
    for (let x of q) {
        r.add(x)
    }
    return r
};


/*
* Identify a right-click.
*
* Note, this is not to be used if your goal is to trigger a context menu.
* For that, you should be binding to the oncontextmenu event. Instead, this
* is intended for cases in which you're trying to handle left-clicks only, and
* need a way to ensure it wasn't a right-click.
*/
util.isRightClick = function(event) {
    return event.which === 3 || event.button === 2
};

/* Set an HTML input element to do NO spell checking, etc.
 */
util.noCorrect = function(elt) {
    elt.setAttribute('autocomplete', 'off');
    elt.setAttribute('autocorrect', 'off');
    elt.setAttribute('autocapitalize', 'off');
    elt.setAttribute('spellcheck', 'false');
};

/* Say how many chars remain, in a textarea.
 *
 * param inputElt: the textarea element whose `maxlength` attr sets
 *   the upper limit
 * param outputElt: an element whose innerText should be set equal to
 *   the number of remaining chars
 * return: function you can call to make the update happen. (It also
 *   happens automatically on the textarea's `input` event, which includes
 *   both editing via keyboard, and copy-paste, incl. via context menu.)
 */
util.showRemainingChars = function(inputElt, outputElt) {
    const M = +inputElt.getAttribute('maxlength');
    function updateChars() {
        outputElt.innerText = M - inputElt.value.length;
    }
    updateChars();
    inputElt.addEventListener('input', updateChars);
    return updateChars;
}

/* Make it so that a dangerous button is activated iff a confirmation string
 * is entered in a corresponding text field.
 *
 * param inputElt: the text input where the conf string must be entered
 * param confString: the string that must be entered, to confirm
 * param buttonElt: the element on which the `dangerButtonDisabled` class
 *   will be added or removed, as appropriate.
 * param goAheadHandler: the function that should be allowed to go ahead
 *   when the button is clicked if and only if the conf string has been entered.
 * return: function you can call to make the activation check happen. (It also
 *   happens automatically on the text fields's `input` event, which includes
 *   both editing via keyboard, and copy-paste, incl. via context menu.)
 */
util.confStringActivatesDangerButton = function(inputElt, confString, buttonElt, goAheadHandler) {
    // I don't think you ever want spell check in this kind of conf input element, so:
    util.noCorrect(inputElt);
    function updateActivation() {
        if (inputElt.value === confString) {
            buttonElt.classList.remove('dangerButtonDisabled');
        } else {
            buttonElt.classList.add('dangerButtonDisabled');
        }
    }
    inputElt.addEventListener('input', updateActivation);
    buttonElt.addEventListener('click', event => {
        if (buttonElt.classList.contains('dangerButtonDisabled')) {
            return;
        } else {
            goAheadHandler(event);
        }
    });
    return updateActivation;
}

/* This function provides an easy way to chain MathJax typeset promises.
 * See <https://docs.mathjax.org/en/latest/web/typeset.html>
 */
util.typeset = function(elements) {
    MathJax.startup.promise = MathJax.startup.promise.then(
        () => MathJax.typesetPromise(elements)
    ).catch(console.error);
    return MathJax.startup.promise;
};

// If you want to instead go back and forth through the server, you would want
// to combine this <https://flask.palletsprojects.com/en/1.1.x/api/#flask.send_file>
// and this <https://docs.python.org/3/library/tempfile.html#examples>.
util.download = function(filename, contents) {
    let href = 'data:text/plain;charset=utf-8,';
    href += encodeURIComponent(contents);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.setAttribute('download', filename);
    a.setAttribute('href', href);
    document.body.appendChild(a);
    a.click();
    a.remove();
};

/* Let the user select a (text) file for upload.
 *
 * param accept: Optional string specifying the types of file accepted.
 *  See <https://developer.mozilla.org/en-US/docs/Web/HTML/Element/input/file#Unique_file_type_specifiers>
 *
 * return: a promise that resolves when the user has selected a file, and
 * its contents have been read.
 */
util.uploadFileContents = function(accept) {
    return new Promise(function(resolve) {
        const i0 = document.createElement('input');
        i0.type = 'file';
        if (accept) i0.accept = accept;
        i0.onchange = function(evt) {
            const fr = new FileReader();
            fr.readAsText(evt.target.files[0], 'UTF-8');
            fr.onload = function(prog_evt) {
                resolve(prog_evt.target.result);
            }
        }
        i0.click();
    });
};

util.openInNewTab = function(url) {
    const win = window.open(url, '_blank');
    win.focus();
}

/* Open a popup window.
 *
 * This calls `window.open()` for you, allowing you to pass a more powerful and flexible
 * set of options, instead of the "features" string required by the built-in function.
 *
 * param url: as in `window.open()`
 * param target: as in `window.open()`
 * param options: You may pass any of the key-value pairs allowed in the "features" string.
 *   In addition, you may use any of the following:
 *     centerX: Set true to make the popup centered in the X-dimension over the parent window.
 *     padX: Set a positive number here in order to not only make the popup centered in the
 *       X-dimension, but to make its width equal to that of the parent window minus twice this padding.
 *     centerY: Like centerX, but for the Y-dimension.
 *     padY: Like padX, but for the Y-dimension.
 * return: the return value of `window.open()`.
 */
util.openPopupWindow = function(url, target, options) {
    const W = window.innerWidth;
    const H = window.innerHeight;
    const L = window.screenLeft;
    const T = window.screenTop;

    let width = options.width || 500;
    let left = options.left || 40;
    if (options.centerX || options.padX) {
        if (options.padX) {
            width = Math.max(20, W - 2 * options.padX);
        }
        left = Math.max(0, L + (W - width)/2);
    }

    let height = options.height || 600;
    let top = options.top || 40;
    if (options.centerY || options.padY) {
        if (options.padY) {
            height = Math.max(20, H - 2 * options.padY);
        }
        top = Math.max(0, T + (H - height)/2);
    }

    options.width = width;
    options.height = height;
    options.left = left;
    options.top = top;
    delete options.centerX;
    delete options.centerY;
    delete options.padX;
    delete options.padY;
    const featureArray = [];
    for (let k in options) {
        let v = options[k];
        featureArray.push(`${k}=${v}`);
    }
    const features = featureArray.join(',');

    return window.open(url, target, features);
}

/* This mix-in can be used to make a class "listenable."
 *
 * Given class `Foo`, you must
 *   1. Ensure `Foo` has a `this.listeners = {}` property (i.e. it's initialized
 *      to be an empty object), and
 *   2. Do
 *          Object.assign(Foo.prototype, util.eventsMixin);
 *
 * Then class `Foo` will be listenable:
 *
 *  Register an event listener:
 *
 *      function barHandler(event) {
 *          //...
 *      }
 *      const f = Foo();
 *      f.on('bar', barHandler);
 *
 *  Event dispatch happens inside some `Foo` method:
 *
 *      Foo.someProcess = function() {
 *          //...
 *          const event = {
 *              type: 'bar',
 *              otherInfo: 'stuff',
 *              moreInfo: 'moreStuff',
 *          }
 *          this.dispatch(event);
 *          //...
 *      }
 *
 * Note that event handling is synchronous, in the sense that every registered
 * event handler function will have been invoked and returned, before any code
 * following `this.dispatch(event)` is executed.
 *
 * If an event handler involves asynchronous processing, and you want it to be
 * awaited, you can say so by passing {await: true} in the options arg to the
 * `on()` call when you register the handler.
 */
util.eventsMixin = {

    /* eventType: string, naming the event you want to listen to
     * callback: function that should be passed the event when it happens
     * options: {
     *  nodup: do not add this callback if it has already been added before,
     *  await: set true if you want the callback to be awaited when it is invoked
     *         (if you think we should just await everything, consider https://stackoverflow.com/a/55263084),
     * }
     */
    on(eventType, callback, options) {
        options = options || {};
        const cbInfos = this.listeners[eventType] || [];
        if (options.nodup && cbInfos.find(info => info.callback === callback)) {
            // FIXME: nodup should be the default.
            //  But we're adding this as afterthought, so must review all
            //  existing usages first.
            return;
        }
        const newInfo = {
            callback: callback,
            await: options.await,
        }
        cbInfos.push(newInfo);
        this.listeners[eventType] = cbInfos;
    },

    off(eventType, callback) {
        const cbInfos = this.listeners[eventType] || [];
        const i0 = cbInfos.findIndex(info => info.callback === callback);
        if (i0 >= 0) {
            cbInfos.splice(i0, 1);
            this.listeners[eventType] = cbInfos;
        }
    },

    async dispatch(event) {
        /* Subtle point: In general, we are always careful not to modify an
         * iterable while we are in the process of iterating over it. Here, we don't
         * know whether a callback might `off` itself as a part of its process,
         * thereby modifying our array of listeners while we are iterating over it!
         * Therefore, to be safe, we have to iterate over a _copy_ of our array of
         * registered listeners. */
        const cbInfos = (this.listeners[event.type] || []).slice();
        for (const info of cbInfos) {
            const cb = info.callback;
            if (info.await) {
                await cb(event);
            } else {
                cb(event);
            }
        }
    },
};

util.getCookie = function(cname) {
    const x = document.cookie.match('(^|;) ?' + cname + '=([^;]*)(;|$)');
    return x ? x[2] : null;
}

util.setCookie = function(cname, val, numDays) {
    const d = new Date();
    d.setTime(d.getTime() + 86400000*numDays);
    document.cookie = cname + "=" + val + ";path=/;expires=" + d.toGMTString();
}

util.deleteCookie = function(cname) { util.setCookie(cname, '', -1); }

/* Load a script by its URL.
 * Return a promise that resolves after the script has finished loading.
 */
util.loadScript = function(url) {
    return new Promise(resolve => {
        const s = document.createElement('script');
        s.src = url;
        s.type = "text/javascript";
        s.onload = resolve;
        s.onreadystatechange = resolve;
        document.querySelector('head').appendChild(s);
    });
};

// Check if an object is a string.
util.isString = function(obj) {
    return typeof obj === 'string' || obj instanceof String;
};

// Escape a string
util.escapeHtml = function(s){
    return new Option(s).innerHTML;
}

// ---------------------------------------------------------------------------
// Utilities for Ace editors

// Translate a PISE theme name into an Ace theme path.
util.getAceThemePath = function(theme) {
    const aceThemeName = theme === 'light' ? 'tomorrow' : 'tomorrow_night_eighties';
    return 'ace/theme/' + aceThemeName;
};

util.applyAceEditorFixes = function(editor) {
    /*
    * We make this setting in response to a console message we otherwise receive:
    *   Automatically scrolling cursor into view after selection change
    *   this will be disabled in the next version
    *   set editor.$blockScrolling = Infinity to disable this message
    */
    editor.$blockScrolling = Infinity;
};

util.reclaimAceShortcutsForPise = function(editor) {
    // Let ctrl-L go to the address bar
    editor.commands.removeCommand('gotoline');
    // We use Ctrl-] and Ctrl-[ to move right and left through the tabs in the active
    // tab group. So we take these away from their default assignments in Ace:
    editor.commands.removeCommand('blockindent');
    editor.commands.removeCommand('blockoutdent');
};

/* The `Editor` and `EditSession` classes in Ace don't seem to offer
 * a method just for detaching their many event listeners, and
 * `Editor.destroy()` doesn't do it either.
 * In particular, the EditSession listens to its Document's "change"
 * event, while the Editor listens to quite a large number of its
 * EditSession's events.
 *
 * If we don't detach all these listeners, when we close and destroy an
 * editor, and if the Document in question
 * is still open in any other editor panes, then we will get a crash the
 * moment we next try to edit that document, as non-existent listeners
 * are called.
 *
 * There _is_ code in the Ace codebase to cleanly detach all the listeners
 * in question, but (as far as I have been able to find) it is only in
 * the methods that set a new EditSession in the Editor, or set a new Document
 * in the EditSession.
 *
 * Therefore our solution is to make a new, empty session and document, and
 * set them in the editor and session (resp.) for the pane that is closing.
 */
util.detachListeners = function(editor, ace) {
    const emptySesh = ace.createEditSession('');
    const emptyDoc = emptySesh.getDocument();
    const sesh = editor.getSession();
    sesh.setDocument(emptyDoc);
    editor.setSession(emptySesh);
};

// ---------------------------------------------------------------------------

return util;
});
