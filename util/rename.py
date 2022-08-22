# --------------------------------------------------------------------------- #
#   Proofscape Server                                                         #
#                                                                             #
#   Copyright (c) 2011-2022 Proofscape contributors                           #
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

import os, re

# Define (regex, substitution) pairs for replacements to be made in
# all modules. The subs. may contain backrefs to matching groups in
# the regex.
pairs = {
	'an_old_name': 'a_new_name',
	r'foo_(\d+)': r'bar_\1',
}

compiled_pairs = []
for k, v in pairs.items():
	r = re.compile(k, flags=re.MULTILINE)
	compiled_pairs.append((r, v))

root = '../'

for P, D, F in os.walk(root):
	for fn in F:
		if fn[-3:] != '.py': continue
		path = os.path.join(P, fn)
		with open(path, 'r') as f:
			text = f.read()
		for r, v in compiled_pairs:
			text = r.sub(v, text)
		with open(path, 'w') as f:
			f.write(text)
