## Basic Operation

Start by choosing a directory where Proofscape can live on your machine. We recommend
`~/proofcape`, but you can choose any directory you want. We'll refer to the
directory you choose as `PFSC_ROOT`.

When making your choice, bear in mind that all of your Proofscape content
repos will live under `PFSC_ROOT/lib`. This means that, if you'll be developing
content, you'll be doing things like git commits in `PFSC_ROOT/lib`.
So, be sure to choose a convenient location.

Once you've made the `PFSC_ROOT` directory, you can start up the container with

```shell
docker run --rm \
     --name=pise \
     -p 7372:7372 \
     -v PFSC_ROOT:/proofscape \
     proofscape/pise:latest
```

**being sure to substitute** the absolute filesystem path to your `PFSC_ROOT`
directory.

You should see some logging output.
When you see a line containing

    INFO success: pfsc_web entered RUNNING state

you can navigate your web browser to ``localhost:7372`` and the Proofscape ISE
should load. We recommend using either Firefox or Chrome.

You can find a fuller set of instructions
[here](https://proofscape.org/pise/running_the_ise/basic.html).


## License

A combined license file, for all the software loaded into each image, can be
found in the image itself, under `/home/pfsc/LICENSES.txt`.
The combined license file for the `latest` image can also be found online at
<https://github.com/proofscape/pfsc-manage/blob/main/topics/pfsc/oca_combined_license_file.txt>.
