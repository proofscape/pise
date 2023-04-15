# --------------------------------------------------------------------------- #
#   Copyright (c) 2011-2023 Proofscape Contributors                           #
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

from collections import defaultdict

from pfsc.build.versions import get_major_version_part
from pfsc.excep import PfscExcep, PECode
from pfsc.lang.doc import DocReference


class PfscObj:
    """
    Implements basic functionality that all objects defined in
    Proofscape modules will have.

    A PfscObj should be thought of as functioning on two levels:
    on the one hand it is a Python object like any other, and it
    stores its own data items as self.X.
    On the other hand, its purpose is to represent an "object"
    defined in a Proofscape "module", and the data which belong
    to it on that level are stored in its self.items dictionary.

    For example, if a deduction called 'Pf' is defined in a
    Proofscape module, then the PfscModule object representing
    that module will have an item in its self.items with
    key 'Pf' and value being an instance of the Deduction class
    representing the 'Pf' deduction.

    The __getitem__ and __setitem__ methods of the PfscObj class
    are designed for easy access to the items declared in the
    Proofscape module. If M were the PfscModule object discussed
    above, then M['Pf'] would return the 'Pf' deduction. If that
    deduction had a node named 'E70' in it, then that Node object
    could be retrieved by M['Pf.E70']. If that node had a subnode
    called 'C1', that could be retrieved by M['Pf.E70.C1'].
    """

    def __init__(self):
        self.items = defaultdict(PfscObj)
        # A libpath is something like 'lib.H.ilbert.ZB.Thm168.Pf'
        self.libpath = None
        # A name is something like 'Pf' -- the final segment of a dotted libpath.
        self.name = ''
        self.parent = None
        self.origin = None

    def listAllItems(self):
        return list(self.items.keys())

    def listItemsMatchingRegex(self, regex):
        """
        :param regex: a compiled regular expression (not a string).
        :return: a list of any and all items defined in this object whose
          name matches the given regex.
        """
        return filter(lambda k: regex.match(k), self.listAllItems())

    def getName(self):
        return self.name

    def getLibpath(self):
        """
        All PfscObjs have a libpath.
        """
        return self.libpath

    def getIntramodularPath(self):
        lp = self.getLibpath()
        mp = self.getModule().getLibpath()
        imp = lp[len(mp):]
        if imp and imp[0] == '.':
            imp = imp[1:]
        return imp

    def getIntradeducPath(self):
        lp = self.getLibpath()
        mp = self.getDeduction().getLibpath()
        imp = lp[len(mp):]
        if imp and imp[0] == '.':
            imp = imp[1:]
        return imp

    def get_NCA_libpath(self, other):
        """
        Compute the libpath of the nearest common ancestor of this object and another.
        For these purposes, an object is considered to be an "ancestor" of itself.
        (Therefore, in particular, if one of the two objects is an ancestor of the other,
        then it is equal to their NCA.)
        @param other: the other object
        @return: the libpath of the NCA
        """
        A = self.getLibpath().split('.')
        B = other.getLibpath().split('.')
        C = []
        for a, b in zip(A, B):
            if a == b:
                C.append(a)
            else:
                break
        nca = '.'.join(C)
        return nca

    def get_fwd_rel_libpath(self, other):
        """
        The "forward relative libpath" from one object to another is the part of the
        relative libpath that comes after the initial dots. Thus,

            OLP = NCA.FRL

        where OLP is the "other's libpath", NCA is the "nearest common ancestor",
        and FRL is the "foward relative libpath".

        @param other: the other object
        @return: the forward relative libpath from this object to the other
        """
        nca = self.get_NCA_libpath(other)
        olp = other.getLibpath()
        n = len(nca)
        # If the two libpaths have any segments in common, then we want to
        # begin the slice one char after the first n chars, in order to skip
        # the next dot. (But if n is zero then there is no dot to skip.)
        begin = n + 1 if n > 0 else 0
        return olp[begin:]

    def cascadeLibpaths(self):
        parentLibpath = ''
        if self.parent:
            parentLibpath = self.parent.getLibpath()
        self.libpath = '%s.%s'%(parentLibpath, self.name)
        for item in self.items.values():
            if callable(getattr(item, 'cascadeLibpaths', None)):
                item.cascadeLibpaths()

    def isNative(self, item, selfNative=True):
        """
        Say whether an item is a PfscObj native to this PfscObj.
        :param item: the item in question
        :param selfNative: say whether this PfscObj should be regarded as native to itself
        :return: boolean
        """
        if not isinstance(item, PfscObj): return False
        slp = self.libpath
        n = len(slp)
        ilp = item.getLibpath()
        m = len(ilp)
        pre = ilp[:n]
        return pre == slp and (
            ( m == n and selfNative) or
            ( m > n and ilp[n] == '.' )
        )

    def getNativeItemsInDefOrder(self):
        """
        Get an ordered dict of all native items in definition order.

        :return: ordered dict of native items
        """
        return {name:item for name, item in self.items.items() if self.isNative(item)}

    def recursiveItemVisit(self, visitor_func):
        """
        Visit all items at and below this PfscObj, recursively. At each item
        (including this one), apply the given visitor function. The latter can
        decide for itself (based on types?) whether to do anything.

        :param visitor_func: the visitor function to be applied to each item.
        :return: nothing
        """
        visitor_func(self)
        native = self.getNativeItemsInDefOrder()
        for item in native.values():
            if callable(getattr(item, 'recursiveItemVisit', None)):
                item.recursiveItemVisit(visitor_func)

    def setOrigin(self, origin):
        self.origin = origin

    def getOrigin(self):
        return self.origin

    def setParent(self, parent):
        self.parent = parent

    def getParent(self):
        return self.parent

    def realObj(self):
        return self

    def getNodeType(self):
        return '---'

    def isModule(self):
        return False

    def isDeduc(self):
        return False

    def isSubDeduc(self):
        return False

    def isNode(self):
        return False

    def isGhostNode(self):
        return False

    def canAppearAsGhostInMesonScript(self):
        return False

    def isSubNode(self):
        return False

    def isModal(self):
        return False

    def get_index_type(self):
        return None

    def get_rhs(self):
        return None

    def getModule(self):
        """
        Get the PfscModule under which this object is nested.
        """
        if self.isModule(): return self
        elif self.parent: return self.parent.getModule()
        else: return None

    def getVersion(self):
        mod = self.getModule()
        if mod is None:
            return None
        return mod.getVersion()

    def getMajorVersion(self, allow_WIP=True):
        vs = self.getVersion()
        return get_major_version_part(vs, allow_WIP=allow_WIP)

    def getDependencies(self):
        return self.getModule().getDependencies()

    def getRequiredVersionOfObject(self, libpath, extra_err_msg='', loading_time=True):
        mod = self.getModule()
        return mod.getRequiredVersionOfObject(libpath, extra_err_msg=extra_err_msg, loading_time=loading_time)

    def getDeduction(self):
        """
        Return the Deduction object to which self belongs,
        or None if none can be found.
        """
        if self.isDeduc(): return self
        elif self.parent: return self.parent.getDeduction()
        else: return None

    def getSubdeduction(self):
        """
        Return the nearest SubDeduc OR Deduction
        object to which self belongs (NOT including self),
        or None if none can be found.
        """
        if self.parent:
            p = self.parent
            if p.isSubDeduc() or p.isDeduc(): return p
            else: return p.getSubdeduction()
        else: return None

    def getSubdeducAncestorSeq(self):
        """
        If the path from Deduction, through SubDeducs, down to
        this object is:
            Ded.Sub1.Sub2...Subn.Obj
        then return the list
            [Ded, Sub1, Sub2, ..., Subn]
        """
        sas = []
        s = self.getSubdeduction()
        if s:
            if not s.isDeduc():
                sas = s.getSubdeducAncestorSeq()
            sas.append(s)
        return sas

    def getDocRef(self):
        return {}

    def getDocRefInternalId(self):
        return self.getLibpath()

    def __getitem__(self, path):
        """
        As in the `get` method, you may access objects within objects by passing a path, and the
        path may be either a list or a dot-delimited string.

        However, as with an ordinary dictionary, when using this method you will get a KeyError if
        the requested path is not found.
        """
        item = self.get(path)
        if item is None:
            msg = "Subobject %s not found in %s" % (path, self.libpath)
            raise PfscExcep(msg, PECode.SUBOBJECT_NOT_FOUND)
        return item

    def __setitem__(self, path, value):
        """
        As in the `get` methods, you can store the value under a path, which may be a list or a
        dot-delimited string.
        """
        if isinstance(path, str):
            path = path.split('.')
        assert isinstance(path, list)
        lead = path[0]
        if len(path) == 1:
            self.items[lead] = value
        else:
            # This works because self.items is a defaultdict(PfscObj)
            self.items[lead][path[1:]] = value

    def lazyLoadSubmodule(self, name):
        """
        If this object is a module, then attempt to load a submodule.
        (See PfscModule class, which overrides.)
        @param name: the name of the supposed submodule
        @return: the loaded submodule, if found, else None
        """
        return None

    def getAsgnValue(self, path, default=None):
        """
        Convenience method to `get` an object (see `get()` method), and then, if
        it turns out to be a PfscObj, return the value of its `get_rhs()` method.
        In the case of a PfscAssignment, this is the "assignment value" referenced
        in the name of this method.
        """
        obj = self.get(path, default=None, lazy_load=False)
        return obj.get_rhs() if isinstance(obj, PfscObj) else default

    def getAsgnValueFromAncestor(self, path, default=None, proper=False, missing_obj_descrip=None):
        """
        Like `getAsgnValue()` only this time we use `getFromAncestor()` instead of `get()`.
        """
        obj, libpath = self.getFromAncestor(path, proper=proper, missing_obj_descrip=missing_obj_descrip)
        obj = obj.get_rhs() if isinstance(obj, PfscObj) else default
        return obj, libpath

    def get(self, path, default=None, lazy_load=True):
        """
        This works like the 'get' function for dict objects in python, except that you can pass a path
        to access objects within objects.

        The path may be either a dot-delimited string, or a list.

        E.g. suppose you have three PfscObjs A, B, and C, with each one belonging to the self.items of
        the former. Then you can use A.get("B.C") or A.get(["B", "C"]) to retrieve C from A.

        :param path: the object path you want to access
        :param default: an object to return if the desired object is not found
        :param lazy_load: if True, and the object is not found, then we will attempt to
            lazy load it as a submodule.
        """
        # Make sure the path is in the form of a list, if not already.
        if isinstance(path, str):
            path = path.split('.')
        assert isinstance(path, list)
        # Check length. A list of zero length is an error.
        n = len(path)
        if n == 0:
            msg = 'Attempt to access item with empty path.'
            raise PfscExcep(msg, PECode.MALFORMED_LIBPATH)
        # So path is at least one segment long.
        # Grab the lead segment.
        lead = path[0]
        # See if we can get an item named by the lead segment.
        item = None
        if lead in self.items:
            # We do have an item.
            item = self.items[lead]
        elif lazy_load:
            # We do not currently have an item named by the lead segment.
            # Last-ditch: see if we can lazy load a submodule by that name.
            item = self.lazyLoadSubmodule(lead)
        # Did we manage to get an item?
        if item is not None:
            # Yes, we got one.
            if n == 1:
                # If that's the whole path, then just return the item.
                return item
            else:
                # If there's more to the path, then recurse.
                return item.get(path[1:], default)
        else:
            # Nope. Time to give up.
            return default

    def getFromAncestor(self, path, proper=False, missing_obj_descrip=None):
        """
        Try to get the item named by the path (list or dotted string).

        If `proper` (as in "proper ancestor") is False, we begin the search with self;
        if true, we begin with self.parent. We work recursively until the item is found
        or until there is no parent.

        If the item is found, return an ordered pair (item, libpath), where the item is the item found,
        and the libpath is that of the "ancestor" that had it -- the "ancestor" may be self.

        If the item is not found, then what we do depends on whether you provided a missing_obj_descrip.
        If this has been provided, then we raise an exception, using this string to help build the error message.
        It should be a descriptive phrase, such as "named in Meson script in deduction <LIBPATH>", that can
        help the user know where the failed reference took place.

        If you did not provide a missing object description, then we assume you want to fail gracefully, so
        we just return an ordered pair, in which both components are None.
        """
        item = None if proper else self.get(path)
        if item is None:
            if self.parent:
                return self.parent.getFromAncestor(path, missing_obj_descrip=missing_obj_descrip)
            elif missing_obj_descrip is not None:
                msg = 'Object "%s" %s could not be found.\n' % (path, missing_obj_descrip)
                msg += 'Did you forget to import it or declare it?'
                raise PfscExcep(msg, PECode.MODULE_DOES_NOT_CONTAIN_OBJECT)
            else:
                return (None, None)
        else:
            return (item, self.libpath)

    def resolve_object(self, obj_path, obj_home, self_typename='', obj_descrip='object', allowed_types=None):
        """
        Attempts to resolve a libpath (possibly relative) to an actual object, within a
        given obj_home. You may optionally check the type of the object. If found (and of
        correct type, if checked), the object is returned. Else an exception is raised.

        @param obj_path: the libpath (possibly relative) of the object to be located
        @param obj_home: a PfscModule in which the given object path should
                       resolve to some object
        @param self_typename: a phrase describing the kind of object this is; for use in
                              error messages
        @param obj_descrip: a phrase describing the kind of object you expect to find; for
                            use in error messages
        @param allowed_types: optional list of allowed types for the object. If not given,
                              we do not impose any type requirement.
        @return: the located object
        """
        allowed_types = allowed_types or []
        obj = obj_home.get(obj_path)
        if not obj:
            msg = 'Named %s "%s" for %s "%s" ' % (
                obj_descrip, obj_path, self_typename, self.name
            )
            msg += 'in obj_home "%s" not defined.' % obj_home.getLibpath()
            raise PfscExcep(msg, PECode.TARGET_DOES_NOT_EXIST)
        if allowed_types:
            for t in allowed_types:
                if isinstance(obj, t):
                    break
            else:
                msg = 'Named %s "%s" for %s "%s" ' % (
                    obj_descrip, obj_path, self_typename, self.name
                )
                msg += 'in obj_home "%s" is of wrong type' % obj_home.getLibpath()
                raise PfscExcep(msg, PECode.TARGET_OF_WRONG_TYPE)
        return obj

class PfscDefn(PfscObj):

    def __init__(self, name, lhs, rhs, module=None):
        PfscObj.__init__(self)
        self.parent = module
        self.name = name
        self.lhs = lhs
        self.rhs = rhs

class Enrichment(PfscObj):
    """
    A PfscObj that provides enrichment. Such objects can have "targets", and the top-level
    entities defined in pfsc modules tend to be of this kind. A Deduction may be "of" targets;
    an Examplorer may be "for" targets; an Annotation may be "on" targets.
    """

    def __init__(self, typename):
        """
        @param typename: a string describing the subtype, e.g. 'deduction'.
        """
        self.typename = typename
        PfscObj.__init__(self)
        self.targets = []
        self.targetDeduc = None
        self.doc_info = None

    def getTargets(self):
        return self.targets

    def getTargetDeduc(self):
        return self.targetDeduc

    def getTargetLibpaths(self):
        lps = []
        if self.targets:
            lps = [t.getLibpath() for t in self.targets]
        return lps

    def gather_doc_info(self, caching=True):
        """
        Do a recursive item visit to build up a doc_info object of the form,
         {
             'docs': {
                 docId1: {
                     ...docInfo1...
                 },
                 docId2: {
                     ...docInfo2...
                 },
             },
             'refs': {
                 docId1: [
                     {...ref1...},
                     {...ref2...},
                 ],
                 docId2: [
                     {...ref3...},
                     {...ref4...},
                 ],
             },
         }
        """
        doc_info = self.doc_info
        if doc_info is None or not caching:
            doc_info = {
                'docs': {},
                'refs': {},
            }
            stype = {
                'deduction': 'CHART',
                'annotation': 'NOTES',
            }.get(self.typename)

            def grabHighlights(obj):
                ref = obj.getDocRef()
                if isinstance(ref, DocReference):
                    doc_id = ref.doc_id
                    if doc_id not in doc_info['docs']:
                        doc_info['docs'][doc_id] = ref.doc_info
                    if doc_id not in doc_info['refs']:
                        doc_info['refs'][doc_id] = []
                    hld = ref.write_highlight_descriptor(
                        obj.getDocRefInternalId(), self.libpath, stype)
                    if hld:
                        doc_info['refs'][doc_id].append(hld)

            self.recursiveItemVisit(grabHighlights)
            if caching:
                self.doc_info = doc_info

        return doc_info

    @staticmethod
    def find_targets(target_paths, module,
                     all_nodes=False, common_deduc=False,
                     typename='', name=''):
        """
        Find the actual objects denoted by a list of target paths, within
        a PfscModule.

        @param target_paths: libpaths (possibly relative) naming targets
        @param module: a PfscModule in which the given target paths should
                       resolve to some object
        @param all_nodes: If True, then all targets must be Nodes.
                          Otherwise, all targets must be either Nodes, Deducs, or Subdeducs.
        @param common_deduc: If True, then all targets are required to belong
                             to a single deduction.
        @param typename: String describing what type of object we are
            ("deduction", "annotation", etc.) For use in error messages.
        @param name: String giving the name of this object. For use in
            error messages.
        @return: pair (T, D), where T is the list of found targets, and D is
            the deduction to which the targets belong if `common_deduc` was
            True, else None.
        """
        # Find the targets.
        targets = []
        for p in target_paths:
            t = module.get(p)
            if not t:
                msg = 'Named target "%s" for %s "%s" ' % (
                    p, typename, name
                )
                msg += 'in module "%s" ' % module.libpath
                msg += 'not defined.'
                raise PfscExcep(msg, PECode.TARGET_DOES_NOT_EXIST)
            n, d, s = t.isNode(), t.isDeduc(), t.isSubDeduc()
            if (all_nodes and not n) or (not (n or d or s)):
                msg = 'Named target "%s" for %s "%s" ' % (
                    p, typename, name
                )
                msg += 'in module "%s" is ' % module.libpath
                if all_nodes:
                    msg += 'not a node. All targets must be nodes.'
                else:
                    msg += 'of wrong type.'
                raise PfscExcep(msg, PECode.TARGET_OF_WRONG_TYPE)
            targets.append(t)
        home = None
        if common_deduc:
            # Enforce the rule that all targets belong to the same Deduction.
            if targets:
                home = targets[0].getDeduction()
                if not home:
                    msg = 'Could not find deduction to which '
                    msg += 'target %s of %s %s belongs.' % (
                        target_paths[0], typename, name
                    )
                    raise PfscExcep(msg, PECode.TARGETED_DEDUC_DOES_NOT_EXIST)
                for t, p in zip(targets[1:], target_paths[1:]):
                    h = t.getDeduction()
                    if h != home:
                        msg = 'Targets %s and %s of %s %s ' % (
                            target_paths[0], p, typename, name
                        )
                        msg += 'appear to belong to different '
                        msg += 'deductions %s and %s.\n' % (home, h)
                        msg += 'All targets are required to '
                        msg += 'belong to a single deduction.'
                        raise PfscExcep(msg, PECode.TARGETS_BELONG_TO_DIFFERENT_DEDUCS)
        return targets, home

    def find_and_store_targets(self, target_paths, module, all_nodes=False, common_deduc=False):
        """
        Convenience method to call `self.find_targets()` and then store the
        results in the correct fields.
        """
        self.targets, self.targetDeduc = self.find_targets(
            target_paths, module,
            all_nodes=all_nodes, common_deduc=common_deduc,
            typename=self.typename, name=self.name
        )
