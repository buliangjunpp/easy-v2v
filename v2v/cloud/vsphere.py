from oslo_log import log as logging
from pyVim import connect
from pyVmomi import vim
from pyVmomi import vmodl
import six

from v2v.common.exception import vSpherePropertyNotExist
from v2v.cloud.base import BaseDriver

LOG = logging.getLogger(__name__)


def build_full_traversal():
    """
    Builds a traversal spec that will recurse through all objects .. or at
    least I think it does. additions welcome.

    See com.vmware.apputils.vim25.ServiceUtil.buildFullTraversal in the java
    API. Extended by Sebastian Tello's examples from pysphere to reach networks
    and datastores.
    """

    TraversalSpec = vmodl.query.PropertyCollector.TraversalSpec
    SelectionSpec = vmodl.query.PropertyCollector.SelectionSpec

    # Recurse through all resourcepools
    rpToRp = TraversalSpec(name='rpToRp', type=vim.ResourcePool,
                           path="resourcePool", skip=False)

    rpToRp.selectSet.extend(
        (
            SelectionSpec(name="rpToRp"),
            SelectionSpec(name="rpToVm"),
        )
    )

    rpToVm = TraversalSpec(name='rpToVm', type=vim.ResourcePool, path="vm",
                           skip=False)

    # Traversal through resourcepool branch
    crToRp = TraversalSpec(name='crToRp', type=vim.ComputeResource,
                           path='resourcePool', skip=False)
    crToRp.selectSet.extend(
        (
            SelectionSpec(name='rpToRp'),
            SelectionSpec(name='rpToVm'),
        )
    )

    # Traversal through host branch
    crToH = TraversalSpec(name='crToH', type=vim.ComputeResource, path='host',
                          skip=False)

    # Traversal through hostFolder branch
    dcToHf = TraversalSpec(name='dcToHf', type=vim.Datacenter,
                           path='hostFolder', skip=False)
    dcToHf.selectSet.extend(
        (
            SelectionSpec(name='visitFolders'),
        )
    )

    # Traversal through vmFolder branch
    dcToVmf = TraversalSpec(name='dcToVmf', type=vim.Datacenter,
                            path='vmFolder', skip=False)
    dcToVmf.selectSet.extend(
        (
            SelectionSpec(name='visitFolders'),
        )
    )

    # Traversal through network folder branch
    dcToNet = TraversalSpec(name='dcToNet', type=vim.Datacenter,
                            path='networkFolder', skip=False)
    dcToNet.selectSet.extend(
        (
            SelectionSpec(name='visitFolders'),
        )
    )

    # Traversal through datastore branch
    dcToDs = TraversalSpec(name='dcToDs', type=vim.Datacenter,
                           path='datastore', skip=False)
    dcToDs.selectSet.extend(
        (
            SelectionSpec(name='visitFolders'),
        )
    )

    # Recurse through all hosts
    hToVm = TraversalSpec(name='hToVm', type=vim.HostSystem, path='vm',
                          skip=False)
    hToVm.selectSet.extend(
        (
            SelectionSpec(name='visitFolders'),
        )
    )

    # Recurse through the folders
    visitFolders = TraversalSpec(name='visitFolders', type=vim.Folder,
                                 path='childEntity', skip=False)
    visitFolders.selectSet.extend(
        (
            SelectionSpec(name='visitFolders'),
            SelectionSpec(name='dcToHf'),
            SelectionSpec(name='dcToVmf'),
            SelectionSpec(name='dcToNet'),
            SelectionSpec(name='crToH'),
            SelectionSpec(name='crToRp'),
            SelectionSpec(name='dcToDs'),
            SelectionSpec(name='hToVm'),
            SelectionSpec(name='rpToVm'),
        )
    )

    fullTraversal = SelectionSpec.Array(
        (visitFolders, dcToHf, dcToVmf, dcToNet, crToH, crToRp, dcToDs, rpToRp,
         hToVm, rpToVm,))

    return fullTraversal


class VMwareDriver(BaseDriver):
    """Initialize a connection to a vcenter"""

    def __init__(self, host='localhost', port=443, user='root', pwd='', **kwargs):
        self._host = host
        self._port = port
        self._user = user
        self._pwd = pwd
        self._kwargs = kwargs
        self.si = None
        if not isinstance(self._port, six.integer_types):
            try:
                self._port = int(self._port)
            except ValueError:
                raise ValueError("The type of port should be integer.")

    def connect(self):
        try:
            self.si = connect.SmartConnect(
                host=self._host,
                port=self._port,
                user=self._user,
                pwd=self._pwd,
                disableSslCertValidation=True
            )
        except Exception as ex:
            LOG.error(f"connet vcenter use host={self._host}, port={self._port}, usr={self._user},"
                      f" pwd={self._pwd} has error={str(ex)}")
        finally:
            if self.si is None:
                LOG.error("Could not connect to the specified vcenter using "
                          "specified username and password")

    def disconnect(self):
        if self.si:
            connect.Disconnect(self.si)
            self.si = None

    def __enter__(self):
        self.connect()
        return self.si

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


class vSphere(VMwareDriver):
    """Some base methods for retrieve exsi/vms/database, etc"""

    def __init__(self, *args, **kwargs):
        super(vSphere, self).__init__(*args, **kwargs)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    @staticmethod
    def _parse_propspec(propspec):
        """Parses property specifications

        :param propspec: The property specifications need to be parsed
        :type propspec: dict
        :returns: a sequence of 2-tuples.
            Each containing a managed object type and a list of properties
            applicable to that type
        """
        props = []
        propspec = propspec or {}
        for objtype, objprops in propspec.items():
            motype = getattr(vim, objtype, None)
            if motype is None:
                raise vSpherePropertyNotExist(motype)
            props.append((motype, objprops,))
        return props

    @staticmethod
    def _create_filter_spec(objs, props):
        """Returns filterSpec object"""
        obj_specs = []
        prop_specs = []
        traversal = build_full_traversal()
        for obj in objs:
            obj_spec = vmodl.query.PropertyCollector.ObjectSpec(obj=obj,
                                                               selectSet=traversal)
            obj_specs.append(obj_spec)
        for motype, proplist in props:
            # param all: bool
            # Specifies whether or not all properties of the object are read.
            # If this properties is set to true, the 'pathSet' property is ignored.
            prop_spec = vmodl.query.PropertyCollector.PropertySpec(all=False,
                                                                   type=motype,
                                                                   pathSet=proplist)
            prop_specs.append(prop_spec)
        filter_spec = vmodl.query.PropertyCollector.FilterSpec(objectSet=obj_specs,
                                                               propSet=prop_specs)
        return filter_spec

    def get_container_view(self, container=None, object_type=None, recursive=True):
        """Returns the container view of specified object type

        :param container: A reference to an instance of a Folder, Datacenter,
                ResourcePool or HostSystem object.
        :type container: ManagedEntity Object
        :param object_type: An optional list of managed entity types. The server
                associates only objects of the specified types with the view.
                If you specify an empty list, the server uses all types.
        :type object_type: List
        :param recursive: When True, include only the immediate children of the
                container instance. When False, include additional objects by
                following paths beyond the immediate children.
        :type recursive: Bool
        """
        if self.si is None:
            return

        container = container or self.si.content.rootFolder
        container_view = self.si.content.viewManager.CreateContainerView(
            container, object_type, recursive
        )
        view = container_view.view
        container_view.Destroy()
        return view

    def _do_property_collector(self, objs, props, max_objects=100):
        """Really do properties collector using RetrievePropertiesEx

        :param objs: The objects will be queried
        :param props: The properties of objects will be queried
        :param max_objects: The maximum number of ObjectContent data objects that should
        be returned in a single result from RetrievePropertiesEx. The default is 100
        """
        if self.si is None:
            return

        pc = self.si.content.propertyCollector
        filter_spec = self._create_filter_spec(objs, props)
        options = vmodl.query.PropertyCollector.RetrieveOptions(maxObjects=max_objects)
        result = pc.RetrievePropertiesEx([filter_spec], options)

        # Because the maximum number of objects retrieved by RetrievePropertiesEx
        # and ContinueRetrievePropertiesEx were limit to 100. So, we need to
        # continue retrieve properties using token
        def _continue(token=None):
            _result = pc.ContinueRetrievePropertiesEx(token)
            _token = _result.token
            _objects = _result.objects
            if _token is not None:
                _objects_ex = _continue(_token)
                _objects.extend(_objects_ex)
            return _objects

        if result is None:
            return []

        token = result.token
        objects = result.objects
        if token is not None:
            _objects = _continue(token)
            objects.extend(_objects)

        return objects

    def property_collector(self, container=None, object_type=None, property_spec=None):
        """Retrieve specified properties of  specified objects

        :param container: A reference to an instance of a Folder, Datacenter,
                ResourcePool or HostSystem object.
        :type container: ManagedEntity Object
        :param object_type: An optional list of managed entity types. The server
                associates only objects of the specified types with the view.
                If you specify an empty list, the server uses all types.
        :type object_type: List
        :param property_spec: The property specifications need to be parsed.
        :type property_spec: dict
        :return: The ObjectContent data objects which retrieved from RetrievePropertiesEx.

        :useage
            with vSphere(host='localhost', user='root', pwd='') as vs:
                container = vs.si.content.rootFolder
                object_type = [vim.Datacenter]
                prop_spec = {
                    "VirtualMachine": ["name"]
                }
                objects = vs.property_collector(container, object_type, prop_spec)
        """
        # The type of object_type must be list
        if not isinstance(object_type, list):
            object_type = [object_type]

        objs = self.get_container_view(container=container, object_type=object_type)
        props = self._parse_propspec(property_spec)
        result = []
        try:
            objects = self._do_property_collector(objs, props)
        except vmodl.query.InvalidProperty:
            raise
        for obj in objects:
            value = dict()
            for prop in obj.propSet:
                value[prop.name] = prop.val
            result.append(value)
        return result
