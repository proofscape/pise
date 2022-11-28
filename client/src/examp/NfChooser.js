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

define([
    "dojo/_base/declare",
    "ise/examp/Chooser"
], function(
    declare,
    Chooser
) {

// NfChooser class
const NfChooser = declare(Chooser, {

    adaptValueForDisplay: function(val) {
        let variable = 'x',
            gen = '\\alpha',
            pol = val;
        // Is it named as cyc(m)?
        if (val.slice(0, 4) === 'cyc(') {
            let m = val.slice(4, -1);
            pol = '\\Phi_{'+m+'}('+variable+')';
            gen = m === '3' ? '\\omega' : '\\zeta';
        } else {
            let letter_match = val.match(/([a-z])/);
            if (letter_match !== null) {
                variable = letter_match[0];
            }
            pol = pol.replaceAll("*", ' ');
        }
        // Write in quotient form.
        let dispVal = `$\\mathbb{Q}(${gen}) \\cong \\mathbb{Q}[${variable}]/(${pol})$`;
        return dispVal;
    },

});

return NfChooser;
});