/* ------------------------------------------------------------------------- *
 *  Copyright (c) 2011-2024 Proofscape Contributors                          *
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

ace.define("ace/mode/proofscape_highlight_rules", [
    "require",
    "exports",
    "module",
    "ace/lib/oop",
    "ace/mode/text_highlight_rules",
    "ace/mode/markdown_highlight_rules",
    "ace/mode/python_highlight_rules"
], function(
    require,
    exports,
    module
) {

"use strict";

var oop = require("../lib/oop");
var TextHighlightRules = require("./text_highlight_rules").TextHighlightRules;
var MarkdownHighlightRules = require("./markdown_highlight_rules").MarkdownHighlightRules;
var PythonHighlightRules = require("./python_highlight_rules").PythonHighlightRules;

var ProofscapeHighlightRules = function() {

    var keywords = (
        "anno|asrt|as|cite|clone|contra|deduc|defn|exis|flse|from|import|intr|" +
        "mthd|of|rels|subdeduc|supp|univ|versus|with|wolog"
    );

    var builtinConstants = (
        "Thm|Pf"
    );

    var builtinFunctions = (
        "de|fr|ru|en|sy|py|cf"
    );
    var keywordMapper = this.createKeywordMapper({
        "invalid.deprecated": "debugger",
        "support.function": builtinFunctions,
        "constant.language": builtinConstants,
        "keyword": keywords
    }, "identifier");

    var mesonInf = 'so|then|therefore|hence|thus|get|infer|find|implies|whence|whereupon';
    var mesonSup = 'by|since|using|because|for';
    var mesonFlow = 'now|next|claim';
    var mesonRoam = 'but|meanwhile|note|have|from|observe|consider';
    var mesonConj = 'and|plus';
    var mesonModal = 'suppose|let';
    var mesonHow = 'applying';

    var MesonInf = 'So|Then|Therefore|Hence|Thus|Get|Infer|Find|Implies|Whence|Whereupon';
    var MesonSup = 'By|Since|Using|Because|For';
    var MesonFlow = 'Now|Next|Claim';
    var MesonRoam = 'But|Meanwhile|Note|Have|From|Observe|Consider';
    var MesonConj = 'And|Plus';
    var MesonModal = 'Suppose|Let';
    var MesonHow = 'Applying';

    //var mesonKeyword = '(?:'+mesonInf+mesonSup+mesonFlow+mesonRoam+mesonConj+mesonModal+mesonHow+')';

    var mesonKeyword = '(?:'+
        [mesonInf, mesonSup, mesonFlow, mesonRoam, mesonConj, mesonModal, mesonHow,
        MesonInf, MesonSup, MesonFlow, MesonRoam, MesonConj, MesonModal, MesonHow].join("|")
        +')';

    //var mesonKeyword = new RegExp(mesonKeywordX, 'i');
    //var mesonKeyword = /suppose|then/i;
    //var mesonKeyword = /(?:suppose|then)/i;

    var strPre = "(?:r|u|ur|R|U|UR|Ur|uR)?";

    /*
    var decimalInteger = "(?:(?:[1-9]\\d*)|(?:0))";
    var octInteger = "(?:0[oO]?[0-7]+)";
    var hexInteger = "(?:0[xX][\\dA-Fa-f]+)";
    var binInteger = "(?:0[bB][01]+)";
    var integer = "(?:" + decimalInteger + "|" + octInteger + "|" + hexInteger + "|" + binInteger + ")";

    var exponent = "(?:[eE][+-]?\\d+)";
    var fraction = "(?:\\.\\d+)";
    var intPart = "(?:\\d+)";
    var pointFloat = "(?:(?:" + intPart + "?" + fraction + ")|(?:" + intPart + "\\.))";
    var exponentFloat = "(?:(?:" + pointFloat + "|" +  intPart + ")" + exponent + ")";
    var floatNumber = "(?:" + exponentFloat + "|" + pointFloat + ")";
    */

    var stringEscape =  "\\\\(x[0-9A-Fa-f]{2}|[0-7]{3}|[\\\\abfnrtv'\"]|U[0-9A-Fa-f]{8}|u[0-9A-Fa-f]{4})";

    this.$rules = {
        "start" : [ {
            token : "comment",
            regex : "#.*$"
        }, /*{
            token : "string",           // multi line """ string start
            regex : strPre + '"{3}',
            next : "qqstring3"
        },*/ {
            token : "string",           // " string
            regex : strPre + '"',
            next : "qqstring"
        },
        /*
        {
            token : "string",           // multi line ''' string start
            regex : strPre + "'{3}",
            next : "qstring3"
        },*/ {
            token : "string",           // ' string
            regex : strPre + "'",
            next : "qstring"
        },
        /*
        {
            token : "constant.numeric", // imaginary
            regex : "(?:" + floatNumber + "|\\d+)[jJ]\\b"
        }, {
            token : "constant.numeric", // float
            regex : floatNumber
        }, {
            token : "constant.numeric", // long integer
            regex : integer + "[lL]\\b"
        }, {
            token : "constant.numeric", // integer
            regex : integer + "\\b"
        },
        */
        {   //token : "keyword",
            token : "support.function",
            regex : "meson\\b",
            next  : "meson"
        }, {
            token : "support.function",
            regex : "anno\\b",
            next  : "anno"
        }, {
            token : "support.function",
            regex : "examp\\b",
            next  : "examp"
        }, {
            token : "constant.language",
            regex : "Pf([0-9_]\\w*)?"
        }, {
            token : keywordMapper,
            regex : "[a-zA-Z_$][a-zA-Z0-9_$]*\\b"
        }, {
            token : "keyword.operator",
            //regex : "\\+|\\-|\\*|\\*\\*|\\/|\\/\\/|%|<<|>>|&|\\||\\^|~|<|>|<=|=>|==|!=|<>|="
            regex : "="
        }, {
            token : "paren.lparen",
            regex : "[\\[\\(\\{]"
        }, {
            token : "paren.rparen",
            regex : "[\\]\\)\\}]"
        }, {
            token: "constant.numeric",
            regex: "<<<<<<<< YOURS|========|>>>>>>>> DISK"
        }, {
            token : "text",
            regex : "\\s+"
        } ],

        /*
        "qqstring3" : [ {
            //token : "constant.language.escape",
            token : "string",
            regex : stringEscape
        }, {
            token : "string", // multi line """ string end
            regex : '"{3}',
            next : "start"
        }, {
            defaultToken : "string"
        } ],

        "qstring3" : [ {
            //token : "constant.language.escape",
            token : "string",
            regex : stringEscape
        }, {
            token : "string",  // multi line ''' string end
            regex : "'{3}",
            next : "start"
        }, {
            defaultToken : "string"
        } ],
        */

        "qqstring" : [ {
            //token : "constant.language.escape",
            token : "string",
            regex : stringEscape
        }, {
            token : "string",
            regex : '"',
            next  : "start"
        }, {
            defaultToken: "string"
        }],

        "qstring" : [ {
            //token : "constant.language.escape",
            token : "string",
            regex : stringEscape
        }, {
            token : "string",
            regex : "'",
            next  : "start"
        }, {
            defaultToken: "string"
        }],

        "meson" : [ {
            token : "keyword.operator",
            regex : "="
        }, {
            token : "string",           // " string
            regex : strPre + '"',
            next : "mesonqqstring"
        }, {
            token : "string",           // ' string
            regex : strPre + "'",
            next : "mesonqstring"
        }],

        "mesonqqstring" : [ {
            token : "keyword",
            //token : "constant.language.escape",
            regex : mesonKeyword
        }, {
            token : "string",
            regex : '"',
            next  : "start"
        }, {
            defaultToken: "string"
        }],

        "mesonqstring" : [ {
            token : "keyword",
            //token : "constant.language.escape",
            regex : mesonKeyword
        }, {
            token : "string",
            regex : "'",
            next  : "start"
        }, {
            defaultToken: "string"
        }],

        "anno" : [ {
            token : "keyword.operator",
            regex : strPre + '@{3}',
            next : "md-start"
        }],

        /*
        "qqstring3" : [ {
            //token : "constant.language.escape",
            token : "string",
            regex : stringEscape
        }, {
            token : "string", // multi line """ string end
            regex : '"{3}',
            next : "start"
        }, {
            defaultToken : "string"
        }]
        */

        "widget_data": [
            // Consume blocks of chars, none of which is {, }, or ".
            { regex: "[^{}\"]+", token: "keyword" },
            // It's important to handle strings separately, since they may contain unmatched braces.
            {   regex: "\"",
                token: "string",
                next: function(currentState, stack){
                    stack.unshift(currentState);
                    return "escaped_string"
                }
            },
            // Open brace: increase depth by pushing another "widget_data" state onto the stack.
            {   regex: "{",
                token: "keyword",
                next: function(currentState, stack){
                    stack.unshift(currentState);
                    return currentState;
                }
            },
            // Close brace:
            {   regex: "}",
                // The token type depends on whether we're about to exit, since we want the outside
                // braces to have a different color.
                onMatch: function(value, currentState, stack){
                    // Any time we are in "widget_data" state, the stack should have
                    // at least two states in it: (1) the state we were in before the
                    // widget began, and (2) just above that, a "widget_data" state.
                    // We do it this way because of the code on line 5236 in ace.js vers. 1.2.0,
                    // which we're using at time of this writing. That line requires at
                    // least _two_ states in the stack, in order to preserve the currentState
                    // across a linebreak. (I don't understand the design; why isn't _one_
                    // state in the stack considered enough?)
                    // Anyway, because we ensure at least those two states are present,
                    // we don't bother checking length of stack before accessing index 1.
                    // `stack[1] !== currentState` means this is the final close brace, and we're about to exit.
                    return stack[1] !== currentState ? "keyword.operator" : "keyword";
                },
                next: function(currentState, stack){
                    // If we're exiting, we have to kick the extra "widget_data" state off
                    // the stack first. Then we can return whatever was the state we were
                    // in before the widget began.
                    if (stack[1] !== currentState) stack.shift();
                    return stack.shift();
                }
            }
        ],

        "escaped_string": [
            { regex: "(\\\\\"|[^\"])+", token: "string" },
            {   regex: "\"",
                token: "string",
                next: function(currentState, stack){
                    return stack.shift();
                }
            }
        ],

        "tex1": [
            { regex: "[^$]+", token: "constant.numeric" },
            {
                regex: "\\$",
                token: "constant.numeric",
                next: function(currentState, stack){
                    // State was pushed twice to preserve it across linebreaks, so must pop twice.
                    stack.shift();
                    return stack.shift();
                }
            }
        ],

        "tex2": [
            { regex: "[^$]+", token: "constant.numeric" },
            {
                regex: "\\$\\$",
                token: "constant.numeric",
                next: function(currentState, stack){
                    // State was pushed twice to preserve it across linebreaks, so must pop twice.
                    stack.shift();
                    return stack.shift();
                }
            }
        ],

    };

    this.embedRules(MarkdownHighlightRules, "md-", [
        {
            token : ["keyword.operator", "keyword", "keyword.operator", "constant.numeric", "keyword.operator"],
            regex : "(<)(chart|ctl|disp|doc|examp|goal|label|link|param|qna)(:)([^>]*)(>\\[)",
            next: function(currentState, stack){
                stack.unshift(currentState);
                return "wlmd-start";
            }
        },
        {
            regex: "\\$\\$?",
            onMatch: function(value, currentState, stack){
                stack.unshift(currentState);
                // We push the state twice, so it will be preserved across linebreaks.
                stack.unshift("tex"+value.length);
                stack.unshift("tex"+value.length);
                return "constant.numeric";
            },
            next: function(currentState, stack){
                return stack.shift();
            }
        },
        {
            token: "constant.numeric",
            regex: "<<<<<<<< YOURS|========|>>>>>>>> DISK"
        },
        {
            token : "keyword.operator",
            regex : '@{3}',
            next : "start"
        }
    ]);

    // Embed Markdown rules again, this time with prefix "wlmd-" for "widget label markdown".
    // These rules will be applied within widget labels.
    this.embedRules(MarkdownHighlightRules, "wlmd-", [
        {
            token : "keyword.operator",
            regex : "\\]{",
            next: function(currentState, stack){
                var next = "widget_data"
                stack.unshift(next);
                return next;
            }
        },
        {
            regex: "\\$\\$?",
            onMatch: function(value, currentState, stack){
                stack.unshift(currentState);
                // We push the state twice, so it will be preserved across linebreaks.
                stack.unshift("tex"+value.length);
                stack.unshift("tex"+value.length);
                return "constant.numeric";
            },
            next: function(currentState, stack){
                return stack.shift();
            }
        },
    ]);

    /* TODO:
     *  This used to be here for the old-style examps.
     *  Now we want python syntax highlighting for the
     *  build string in a disp widget. So, we'll need to
     *  embed the py- rules. Keeping this here until then...
     */
    this.embedRules(PythonHighlightRules, "py-", [
        {
            token : "string", // multi line """" string end
            regex : '"{4}',
            next : "start"
        }
    ]);

};

oop.inherits(ProofscapeHighlightRules, TextHighlightRules);

exports.ProofscapeHighlightRules = ProofscapeHighlightRules;
});

ace.define("ace/mode/folding/proofscape",["require","exports","module","ace/lib/oop","ace/mode/folding/fold_mode"], function(require, exports, module) {
"use strict";

var oop = require("../../lib/oop");
var BaseFoldMode = require("./fold_mode").FoldMode;

var FoldMode = exports.FoldMode = function(markers) {
    this.foldingStartMarker = new RegExp("([\\[{])(?:\\s*)$|(" + markers + ")(?:\\s*)(?:#.*)?$");
};
oop.inherits(FoldMode, BaseFoldMode);

(function() {

    this.getFoldWidgetRange = function(session, foldStyle, row) {
        var line = session.getLine(row);
        var match = line.match(this.foldingStartMarker);
        if (match) {
            if (match[1])
                return this.openingBracketBlock(session, match[1], row, match.index);
            if (match[2])
                return this.indentationBlock(session, row, match.index + match[2].length);
            return this.indentationBlock(session, row);
        }
    }

}).call(FoldMode.prototype);

});

ace.define("ace/mode/matching_brace_outdent",["require","exports","module","ace/range"], function(require, exports, module) {
"use strict";

var Range = require("../range").Range;

var MatchingBraceOutdent = function() {};

(function() {

    this.checkOutdent = function(line, input) {
        if (! /^\s+$/.test(line))
            return false;

        return /^\s*\}/.test(input);
    };

    this.autoOutdent = function(doc, row) {
        var line = doc.getLine(row);
        var match = line.match(/^(\s*\})/);

        if (!match) return 0;

        var column = match[1].length;
        var openBracePos = doc.findMatchingBracket({row: row, column: column});

        if (!openBracePos || openBracePos.row == row) return 0;

        var indent = this.$getIndent(doc.getLine(openBracePos.row));
        doc.replace(new Range(row, 0, row, column-1), indent);
    };

    this.$getIndent = function(line) {
        return line.match(/^\s*/)[0];
    };

}).call(MatchingBraceOutdent.prototype);

exports.MatchingBraceOutdent = MatchingBraceOutdent;
});



ace.define("ace/mode/proofscape",["require","exports","module","ace/lib/oop","ace/mode/text","ace/mode/proofscape_highlight_rules","ace/mode/folding/proofscape","ace/mode/matching_brace_outdent","ace/range"], function(require, exports, module) {
"use strict";

var oop = require("../lib/oop");
var TextMode = require("./text").Mode;
var ProofscapeHighlightRules = require("./proofscape_highlight_rules").ProofscapeHighlightRules;
var ProofscapeFoldMode = require("./folding/proofscape").FoldMode;
var MatchingBraceOutdent = require("./matching_brace_outdent").MatchingBraceOutdent;
var Range = require("../range").Range;

var Mode = function() {
    this.HighlightRules = ProofscapeHighlightRules;
    this.$outdent = new MatchingBraceOutdent();
    this.foldingRules = new ProofscapeFoldMode("\\:");
};
oop.inherits(Mode, TextMode);

(function() {

    this.lineCommentStart = "#";

    this.getNextLineIndent = function(state, line, tab) {
        var indent = this.$getIndent(line);

        var tokenizedLine = this.getTokenizer().getLineTokens(line, state);
        var tokens = tokenizedLine.tokens;

        if (tokens.length && tokens[tokens.length-1].type == "comment") {
            return indent;
        }

        if (state == "start") {
            var match = line.match(/^.*[\{\(\[\:]\s*$/);
            if (match) {
                indent += tab;
            }
        }

        return indent;
    };

    this.checkOutdent = function(state, line, input) {
        return this.$outdent.checkOutdent(line, input);
    };

    this.autoOutdent = function(state, doc, row) {
        this.$outdent.autoOutdent(doc, row);
    };

    /*
    var outdents = {
        "pass": 1,
        "return": 1,
        "raise": 1,
        "break": 1,
        "continue": 1
    };
    
    this.checkOutdent = function(state, line, input) {
        if (input !== "\r\n" && input !== "\r" && input !== "\n")
            return false;

        var tokens = this.getTokenizer().getLineTokens(line.trim(), state).tokens;
        
        if (!tokens)
            return false;
        do {
            var last = tokens.pop();
        } while (last && (last.type == "comment" || (last.type == "text" && last.value.match(/^\s+$/))));
        
        if (!last)
            return false;
        
        return (last.type == "keyword" && outdents[last.value]);
    };

    this.autoOutdent = function(state, doc, row) {
        
        row += 1;
        var indent = this.$getIndent(doc.getLine(row));
        var tab = doc.getTabString();
        if (indent.slice(-tab.length) == tab)
            doc.remove(new Range(row, indent.length-tab.length, row, indent.length));
    };
    */

    this.$id = "ace/mode/proofscape";
}).call(Mode.prototype);

exports.Mode = Mode;
});
