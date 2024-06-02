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

const dragula = require("dragula");

/* Form a Dragula instance in which the content area of each content panel in PISE
 * is made into a valid drop area.
 *
 * You can define your own `isContainer()` and `accepts()` functions as you ordinarily would;
 * we automatically disjoin the option of being a content panel overlay into each of these.
 *
 * param dragulaOptions: options object as you would ordinarily pass to the dragula constructor.
 * param options: as you would pass to the `setupPanelDragTargetOverlays` function defined below.
 *
 * return: dragula instance
 */
export function dragulaWithContentPanelOverlays(dragulaOptions, options) {
    const isContainerOther = dragulaOptions.isContainer || (el => false);
    const acceptsOther = dragulaOptions.accepts || ((el, target, source, sibling) => false);
    dragulaOptions.isContainer = el => (
        el.classList.contains('panelDragTargetOverlay') || isContainerOther(el)
    );
    // We have to let the overlays accept, or else the drake's 'over' and 'out'
    // events won't even be fired on them; however, users can still call
    // `drake.cancel()` in their onDrop handler, if they don't actually want the panel to accept.
    dragulaOptions.accepts = (el, target, source, sibling) => (
        target.classList.contains('panelDragTargetOverlay') || acceptsOther(el, target, source, sibling)
    );
    const drake = dragula(dragulaOptions);
    setupPanelDragTargetOverlays(drake, options);
    return drake;
}

/* Set up event handling on a Dragula instance to make it support
 * drag and drop onto content panel overlays.
 *
 * NOTE: You must include
 *   el.classList.contains('panelDragTargetOverlay')
 * as a disjunctive option in your `isContainer()` function, and
 *   target.classList.contains('panelDragTargetOverlay')
 * likewise in your `accepts()` function. (Note: the first is on `el`, the
 * second is on `target`.)
 *
 * param drake: your Dragula instance
 * param options: {
 *   socketSelector: CSS selector, default '.cpSocket'. Use this to control
 *      on which sockets the panels are added. E.g. could use '.cpSocket.notesSocket'
 *      to limit it to just NOTES panels.
 *   onDrop: You can set a callback function to handle the drop event. It will be passed
 *      *six* arguments:
 *          (drake, el, target, source, sibling, paneId)
 *      `drake` is the dragula instance; next are the usual four of
 *      `el, target, source, sibling` from dragula,
 *      and finally `paneId`. If the item was dropped onto a panel overlay, then the
 *      `paneId` argument will be that panel's dijit pane id. Otherwise it will be `null`.
 * }
 */
export function setupPanelDragTargetOverlays(drake, options) {
    const {
        socketSelector = '.cpSocket',
        onDrop = (drake, el, target, source, sibling, paneId) => {},
    } = (options || {});
    // When drag begins, throw an overlay on top of each panel content area, to serve
    // as a drop target. When drag ends, remove these.
    drake.on('drag', (el, source) => {
        document.querySelectorAll(socketSelector).forEach(p => {
            const overlay = document.createElement('div');
            overlay.classList.add('panelDragTargetOverlay');
            // Because 'dragend' will be fired before 'drop', we have to stash the
            // pane id as a data attribute now (it will be inaccessible later).
            overlay.setAttribute('data-target-id', p.parentElement.id);
            p.appendChild(overlay);
        });
    });
    drake.on('dragend', el => {
        document.querySelectorAll(socketSelector).forEach(p => {
            p.querySelectorAll('.panelDragTargetOverlay').forEach(e => e.remove());
        });
    });

    // Need brute-force hover for the overlays, since the drake "mirror" element for the drag
    // prevents the mouse pointer from being seen as hovering over the panel overlays. For the
    // same reason, we can't use mouseover/out handlers on (any element of) the panels either,
    // which is why we need the overlays in the first place.
    drake.on('over', (el, container, source) => {
        if (container.classList.contains('panelDragTargetOverlay')) {
            container.classList.add('hovered');
        }
    });
    drake.on('out', (el, container, source) => {
        if (container.classList.contains('panelDragTargetOverlay')) {
            container.classList.remove('hovered');
        }
    });

    drake.on('drop', (el, target, source, sibling) => {
        let paneId = null;
        if (target?.classList.contains('panelDragTargetOverlay')) {
            paneId = target.getAttribute('data-target-id');
        }
        onDrop(drake, el, target, source, sibling, paneId);
    });

}
