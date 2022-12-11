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

import { FetchResolvedNotOkError } from "browser-peers/src/errors";

define([], function(){

    const errors = {};

    // ----------------------------------------------------------------------------------
    /* PfscInsufficientPdfServiceError
     *
     * Represents cases in which a service with which we could have potentially obtained
     * a PDF turned out to be either not present, or disabled, or blocked by CORS,
     * or in some other way unable to do what it wants to do.
     */
    errors.PfscInsufficientPdfServiceError = function(message) {
        this.message = message;
        this.stack = Error().stack;
        this.subErrors = [];
    };
    errors.PfscInsufficientPdfServiceError.prototype = Object.create(Error.prototype);
    errors.PfscInsufficientPdfServiceError.prototype.name = "PfscInsufficientPdfServiceError";

    /*
     * It may be useful to be able to record "sub errors," i.e. other errors, perhaps incurred
     * during multiple steps of an attempt to provide a service, all of which add up to the reason
     * why the overall service was ultimately insufficient.
     *
     * For example, the PdfManager class attempts three ways of obtaining a PDF. If all three fail,
     * it may be useful to report the three separate failure messages as sub errors of one overall
     * PfscInsufficientPdfServiceError instance.
     */
    errors.PfscInsufficientPdfServiceError.prototype.addSubError = function(subError) {
        this.subErrors.push(subError);
    };

    // ----------------------------------------------------------------------------------
    /* PfscHttpError
     *
     * Represents an HTTP error, i.e. a status code in the 400-599 range.
     */
    errors.PfscHttpError = function(message) {
        this.message = message;
        this.stack = Error().stack;
    };
    errors.PfscHttpError.prototype = Object.create(Error.prototype);
    errors.PfscHttpError.prototype.name = "PfscHttpError";

    // ----------------------------------------------------------------------------------
    // Groupings and convenience functions

    /*
     * Say whether a given Error is of any of the types we use to represent HTTP errors.
     */
    errors.isHttpError = function(error) {
        return (
            error instanceof FetchResolvedNotOkError ||
            error instanceof errors.PfscHttpError
        );
    };

    errors.throwIfHttpError = function(error) {
        if (errors.isHttpError(error)) throw error;
    };

    // ----------------------------------------------------------------------------------
    /* Here we replicate any error codes defined by the server that
     * we want to be able to recognize in the client.
     */
    errors.serverSideErrorCodes = {
        DOWNLOAD_FAILED: 37,
        PDF_PROXY_SERVICE_DISABLED: 38,
        SSNR_SERVICE_DISABLED: 47,
        HOSTING_REQUEST_REJECTED: 52,
        HOSTING_REQUEST_UNNECESSARY: 54,
        BAD_URL: 137,
        LIBSEG_UNAVAILABLE: 149,
        BAD_PARAMETER_RAW_VALUE_WITH_BLAME: 193,
        MISSING_DASHGRAPH: 229,
        MISSING_ANNOTATION: 230,
    };

    return errors;

});
