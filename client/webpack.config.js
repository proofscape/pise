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

const path = require("path");
const webpack = require('webpack');
const CopyWebpackPlugin = require("copy-webpack-plugin");
const DojoWebpackPlugin = require('dojo-webpack-plugin');

module.exports = env => {
    const devmode = !!(env||{}).dev;
    const releaseMode = !!(env||{}).rel;

    const packageLock = require('./package-lock.json');

    return {
        entry: {
            ise: './src/main.js',
            mathworker: './src/mathworker.js',
        },
        output: {
            filename: `ise/[name].bundle${devmode ? '.' : '.min.'}js`,
        },
        mode: devmode ? 'development' : 'production',
        devtool: devmode ? 'eval-cheap-source-map' : undefined,
        module: {
            rules: [
                {
                    test: /\.css$/,
                    use: [
                        'style-loader',
                        'css-loader'
                    ]
                },
                {
                    test: /\.(png|gif|ico)$/,
                    type: 'asset/inline',
                },
                {
                    test: /piseAboutDialogContents.js$/,
                    use: [
                        {
                            loader: path.resolve('genabout.js')
                        }
                    ]
                }
            ]
        },
        plugins: [
            new webpack.DefinePlugin({
                // See https://stackoverflow.com/a/29252400
                PISE_VERSION: JSON.stringify(process.env.npm_package_version),
                MATHJAX_VERSION: JSON.stringify(packageLock.dependencies["mathjax"].version),
                ELKJS_VERSION: JSON.stringify(packageLock.dependencies["elkjs"].version),
            }),
            new DojoWebpackPlugin({
                loaderConfig: function(env) {
                    return {
                        //baseUrl: '.',
                        packages: [
                            {
                                name: 'dojo',
                                location: env.dojoRoot + '/dojo'
                            },
                            {
                                name: 'dijit',
                                location: env.dojoRoot + '/dijit'
                            },
                            {
                                name: 'dojox',
                                location: env.dojoRoot + '/dojox'
                            },
                        ],
                        paths: {
                            ise: "src"
                        },
                        //deps: ["src/bootstrap"]
                    };
                },
                environment: {dojoRoot: "static"},
                buildEnvironment: {dojoRoot: "node_modules"},
                noConsole: true,  // quiet the console noise on build
                // After switching to Webpack 5 and dojo-webpack-plugin 3, we need this setting, or else we have
                // multiple build errors, regarding modules (e.g. 'url', 'http', 'stream') that cannot be found.
                ignoreNonModuleResources: true,
            }),
            new CopyWebpackPlugin({
                patterns:[
                    {
                        context: "src",
                        from: "img/logo/pies_pise.ico",
                        to: "ise/favicon.ico"
                    },
                    {
                        context: "src",
                        from: "content_types/pdf/pdf.css",
                        to: "ise/pdf.css"
                    },
                    {
                        context: "src",
                        from: "img/icons/loading-icon.gif",
                        to: "ise/loading-icon.gif"
                    },
                ].concat(
                    releaseMode ? [] : [
                        {
                            context: "node_modules",
                            from: "dojo/resources/blank.gif",
                            to: "dojo/resources"
                        },
                        // ------------------------------------------------------------------------
                        // These packages are used in production and ordinary development. But they
                        // are not included in a production dist, which is meant to include only our
                        // own code.
                        {
                            context: "node_modules",
                            from: "mathjax/es5/tex-svg.js",
                            to: "mathjax"
                        },
                        {
                            context: "node_modules/elkjs/lib",
                            from: "elk.bundled.js",
                            to: "elk"
                        },
                        // ------------------------------------------------------------------------
                        // For development/debugging within ELK:
                        {
                            context: "node_modules/elkjs/lib",
                            from: "elk-(api|worker).js",
                            to: "elk"
                        },
                    ]
                ),
            }),
            new webpack.NormalModuleReplacementPlugin(
				/^css!/, function(data) {
					data.request = data.request.replace(/^css!/, "!style-loader!css-loader!")
				}
			),
        ],
    };
};

