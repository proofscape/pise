Blah blah <chart:>[label text]{
    "data": "goes here"
} and yadda yadda yadda <chart:w1>[label]{
    "foo": "bar"
} and now let's just have a bunch of widgets with names:
    <chart:w3>[foo]{}
    <chart:w4>[bar]{}
    <chart:w6>[spam]{}
and now a bunch without names:
    <chart:>[cat]{}
    <chart:>[rat]{}
    <chart:>[hat]{}
okay. So the names `w1`, `w3`, `w4`, and `w6`
have been used, and we have four widgets without
names. We expect the latter to be given the
names `w2`, `w5`, `w7`, and `w8`.
