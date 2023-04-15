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
    "dojo/_base/declare",
    "dojo/query",
    "ise/util",
], function(
    declare,
    query,
    iseUtil
) {

/* Chooser base class
 *
 * This chooser class is designed to support any number of buttons, and up to one dropdown and one text field.
 * In future we may want to write a more general base class to handle more dropdowns and text fields.
 */
const Chooser = declare(null, {

    // Properties

    parent: null,
    elt: null,
    eltQ: null,
    pane: null,
    value_slot: null,
    value: null,
    selectedEltQ: null,

    buttons: null,
    dropdown: null,
    textfield: null,

    hasButtons: null,
    hasDropdown: null,
    hasTextfield: null,

    enabled: null,

    currentTextValue: null,

    listeners: null,


    // Methods

    constructor: function(parent, elt, pane) {
        this.parent = parent;
        this.elt = elt;
        this.eltQ = query(elt);
        this.pane = pane;
        this.value_slot = this.eltQ.query('.param_val');
        this.listeners = {};

        this.grabInputs();
        this.initValue();
        this.activate();
        this.enabled = true;
    },

    enable: function(b) {
        this.enabled = b;
        if (this.hasDropdown) this.dropdown[0].disabled = !b;
        if (this.hasTextfield) this.textfield[0].disabled = !b;
    },

    // ------------------------------------------
    // Subclasses should override

    grabInputs: function() {
        this.buttons = this.eltQ.query('.radio_panel_button');
        this.dropdown  = this.eltQ.query('.dd');
        this.ddnullopt = this.eltQ.query('.dd_null_opt');
        this.textfield = this.eltQ.query('.textfield');
        this.hasButtons = this.buttons.length > 0;
        this.hasDropdown = this.dropdown.length > 0;
        this.hasTextfield = this.textfield.length > 0;

        // Turn off spell check etc. if we have a textfield.
        if (this.hasTextfield) {
            iseUtil.noCorrect(this.textfield[0]);
        }
    },

    initValue: function() {
        this.discoverSelection();
    },

    // ------------------------------------------
    // Selection Discovery

    /*
     * Find out what's selected (button, dropdown, or text), and record it.
    */
    discoverSelection: function() {
        let selected_button = this.getSelectedButton();
        if (selected_button!==null) {
            this.value = selected_button.attr('value')[0];
            this.selectedEltQ = selected_button;
            return;
        }
        let selected_option = this.getSelectedDropdownOption();
        if (selected_option!==null) {
            this.value = selected_option.attr('value')[0];
            this.selectedEltQ = selected_option;
            return;
        }
        let text = this.hasTextfield ? this.textfield.val() : '';
        if (text.length > 0) {
            this.value = this.textfield.val();
            this.selectedEltQ = this.textfield;
            return;
        }
        this.value = null;
        this.selectedEltQ = null;
    },

    /*
     * Return the selected button (query object) if any; else null.
    */
    getSelectedButton: function() {
        let selected_button = this.eltQ.query('.rpb_selected');
        return selected_button.length===1 ? selected_button : null;
    },

    /*
     * Return the selected dropdown option (query object) if any; else null.
    */
    getSelectedDropdownOption: function() {
        if (this.hasDropdown) {
            let e = this.dropdown[0];
            return query(e.options[e.selectedIndex]);
        } else {
            return null;
        }
    },

    /*
     * Return a boolean saying whether the null dropdown option is selected.
    */
    dropdownIsNull: function() {
        return this.dropdown[0].selectedIndex === 0;
    },

    // ------------------------------------------
    // Event Handling

    // Activate the input elements.
    activate: function() {
        // Prepare handlers.
        // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Function/bind
        let b_handler = this.clickButton.bind(this),
            d_handler = this.dropdownChangeHandler.bind(this),
            t_handler = this.typeText.bind(this),
            tk_handler = this.textboxKeyUp.bind(this),
            tb_handler = this.textboxBlur.bind(this),
            tf_handler = this.textboxFocus.bind(this),
            k_handler = this.keyUp.bind(this);
        // Keys
        this.eltQ.on('keyup', k_handler);
        // Buttons
        if (this.hasButtons) {
            this.buttons.on('click', function(event) {
                let button_elt = this;
                b_handler(event, button_elt);
            });
            // Also want pressing Enter when a button has focus to equate
            // to clicking the button.
            this.buttons.on('keyup', function(event) {
                if (event.key==="Enter") {
                    let button_elt = this;
                    b_handler(event, button_elt);
                }
            });
        }
        // Dropdown
        if (this.hasDropdown) this.dropdown.on('change', d_handler);
        // Textfield
        if (this.hasTextfield) {
            this.textfield.on('input', t_handler);
            this.textfield.on('blur', tb_handler);
            this.textfield.on('focus', tf_handler);
            this.textfield.on('keyup', tk_handler);
        }
    },

    // Handle button click.
    clickButton: function(event, button_elt) {
        if (!this.enabled) return;
        // If already selected, do nothing.
        if (this.selectedEltQ && button_elt===this.selectedEltQ[0]) return;
        // Otherwise select this button.
        let button = query(button_elt);
        this.selectButton(button);
        // Give button focus so hitting Enter works.
        button[0].focus();
    },

    // Handle change in the dropdown.
    dropdownChangeHandler: function() {
        if (!this.enabled) return;
        //console.log('dd change');
        //return;
        if (this.dropdownIsNull()) {
            // Value has changed to null.
            this.clearValue();
        } else {
            let sel = this.getSelectedDropdownOption();
            if (sel!==this.selectedEltQ) {
                // A new dropdown element has been selected.
                this.selectDropdownOption(sel);
            }
        }
    },

    // Handle typing in the text field.
    typeText: function() {
        if (!this.enabled) return;
        // Nothing for now.
    },

    textboxKeyUp: function(event) {
        if (!this.enabled) return;
        if (event.key === "Enter") {
            this.textfield[0].blur();
        }
        else if (event.key === "Escape") {
            this.textfield.val(this.currentTextValue);
            this.textfield[0].blur();
        }
    },

    textboxFocus: function(event) {
        if (!this.enabled) return;
        this.currentTextValue = this.textfield.val();
    },

    textboxBlur: function(event) {
        if (!this.enabled) return;
        let v = this.textfield.val();
        if (v !== this.value) {
            this.selectTextfield();
        }
    },

    keyUp: function(event) {
        if (!this.enabled) return;
        // Nothing for now.
    },

    // ------------------------------------------
    // Programmatic Input Clearing and Selection

    selectButton: function(button) {
        // Clear all input elements.
        this.clearButtons();
        this.clearDropdown();
        this.clearTextfield();
        // Select button
        button.addClass('rpb_selected');
        this.selectedEltQ = button;
        // Set value
        let v = button.attr('value')[0];
        let d = button.attr('display')[0];
        this.setValue(v, d);
    },

    selectDropdownOption: function(option) {
        // Clear other input types
        this.clearButtons();
        this.clearTextfield();
        this.clearSelectedAttributesFromDropdown();
        // Record selection
        this.selectedEltQ = option;
        // Record in HTML for copying to another pane:
        option[0].setAttribute('selected', '');
        // Set value
        let v = option.attr('value')[0];
        this.setValue(v);
    },

    selectTextfield: function() {
        // Clear other input types
        this.clearButtons();
        this.clearDropdown();
        // Record selection
        this.selectedEltQ = this.textfield;
        // Set value
        let v = this.textfield.val();
        // We record it in the HTML so it can be easily copied to another pane:
        this.textfield[0].setAttribute('value', v);
        if (v.length === 0) {
            this.clearValue();
        } else {
            this.setValue(v);
        }
    },

    // Ensure no radio panel buttons are selected.
    clearButtons: function() {
        let sel = this.getSelectedButton();
        if (sel!==null) sel.removeClass('rpb_selected');
    },

    clearSelectedAttributesFromDropdown: function() {
        if (this.hasDropdown) {
            for (let opt of this.dropdown.query('option')) {
                opt.removeAttribute('selected');
            }
        }
    },

    // Reset the dropdown to its null option.
    clearDropdown: function() {
        if (this.hasDropdown) {
            this.clearSelectedAttributesFromDropdown();
            let e = this.dropdown[0];
            e.selectedIndex = 0;
        }
    },

    // Clear the text field.
    clearTextfield: function() {
        this.textfield.val('');
    },

    // ------------------------------------------
    // Value Management

    clearValue: function() {
        this.setValue(null);
    },

    setValue: function(v, d) {
        const existingValue = this.value;
        this.value = v;
        let dispVal = null;
        if (d) {
            dispVal = d;
        } else if (v !== null) {
            dispVal = this.adaptValueForDisplay(v);
        }
        this.displayValue(dispVal);
        if (this.value !== existingValue) {
            this.dispatch({
                type: 'change',
                chooser: this,
                value: this.value,
            });
        }
    },

    getValue: function() {
        return this.value;
    },

    /* Turn a parameter value into something appropriate for display.
     * Return value must at least be concat-able with string; if you want it to be typeset, then
     * it must be a string starting with `$`.
     * Subclasses may want to override.
     */
    adaptValueForDisplay: function(v) {
        return "$"+v+"$";
    },

    // Display a value for the parameter.
    //
    // dispVal: a representation of the value for this parameter.
    //          Must be concat-able with string.
    displayValue: function(dispVal) {
        let html = dispVal == null ? '' : '&nbsp;=&nbsp;' + dispVal;
        this.value_slot.innerHTML(html);
        let typeset = typeof(dispVal) === 'string' && dispVal[0] === "$";
        if (typeset) this.typesetDisplayedValue();
    },

    typesetDisplayedValue: function() {
        let elt = this.value_slot[0];
        iseUtil.typeset([elt]);
    },

    getDisplayedValueHtml: function() {
        return this.value_slot.length ? this.value_slot.innerHTML() : '';
    },

});

Object.assign(Chooser.prototype, iseUtil.eventsMixin);

return Chooser;
});