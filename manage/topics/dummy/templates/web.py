# --------------------------------------------------------------------------- #
#   Copyright (c) 2011-2024 Proofscape Contributors                           #
#                                                                             #
#   Licensed under the Apache License, Version 2.0 (the "License");           #
#   you may not use this file except in compliance with the License.          #
#   You may obtain a copy of the License at                                   #
#                                                                             #
#       http://www.apache.org/licenses/LICENSE-2.0                            #
#                                                                             #
#   Unless required by applicable law or agreed to in writing, software       #
#   distributed under the License is distributed on an "AS IS" BASIS,         #
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  #
#   See the License for the specific language governing permissions and       #
#   limitations under the License.                                            #
# --------------------------------------------------------------------------- #

from flask import Flask

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'

page = """
<html>
<head>
<title>%(title)s</title>
<style>
body {
    background: #222;
    color: #eee;
}
</style>
</head>
<body>
<p>Hello World</p>
<p>
This is the dummy pfsc web app.
</p>
</body>
</html>
"""

@app.route("/")
def index():
    return page % {'title': 'index'}

@app.route("/ise")
def ise():
    return page % {'title': 'ise'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7372, debug=True, use_reloader=True)
