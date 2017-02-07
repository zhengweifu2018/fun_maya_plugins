# -*- coding: utf-8 -*-
import maya.api.OpenMaya as nm
import maya.OpenMaya as om
import maya.cmds as cmds
import meshFileManager, common, uuid, time, json, os, shutil
import pymel.core as pm
reload(common)
class ImportAndExport(object):
    '''初始化方法'''
    def __init__(self):
        self.meshFileManager = meshFileManager.MeshFileManager();
        self.out_uv = True
        self.out_normal = True
        self.init()

    def init(self):
        self.geometries = []
        self.materials = []
        self.materialName2UUID = {}
        self.textures = []
        self.textureName2UUID = {}
        self.faceMaterials = []
        self.objectTree = {'type': 'Group', 'children': []}

    def intoTexture(self, copyFolder, materialObject, material, srcProp, distProp):
        # print material.attr(srcProp).inputs()
        _inputs = material.attr(srcProp).inputs()
        if len(_inputs) > 0:
            _input = _inputs[0]
            print _input.type()
            if _input.type() == 'bump2d':
                _cinputs = _input.bumpValue.inputs()
                if len(_cinputs) > 0:
                    if _input.getAttr('bumpInterp') > 0:
                        distProp = 'normalMap'
                    else:
                        materialObject['bumpScale'] = _input.getAttr('bumpDepth')
                        distProp = 'bumpMap'
                    _input = _cinputs[0]
            if _input.type() == 'file':
                _textureUrl = _input.getAttr('fileTextureName')
                if os.path.isfile(_textureUrl):
                    if _input not in self.textureName2UUID:
                        if not os.path.isdir(copyFolder):
                            os.makedirs(copyFolder)
                        shutil.copy(_textureUrl, copyFolder)
                        _uuidTex = str(uuid.uuid3(uuid.NAMESPACE_DNS, `time.time()`))
                        materialObject[distProp] = _uuidTex
                        self.textureName2UUID[_input] = _uuidTex
                        # print ;
                        _textureObject = {
                           'uuid': _uuidTex, 
                           'url': './textures/' + os.path.basename(_textureUrl)
                        }

                        self.textures.append(_textureObject)
                    else:
                        materialObject[distProp] = self.textureName2UUID[_input]

    def loopFind(self, tObject, treeParent):
        _type = tObject.apiType()
        # print tObject.hasFn(om.MFn.kTransform) and tObject.hasFn(om.MFn.kMesh)
        if _type == om.MFn.kTransform:
            _transform = om.MFnTransform(tObject)
            # print _transform.name(), tObject.hasFn(om.MFn.kMesh)
            if 'children' not in treeParent:
                treeParent['children'] = []

            _object = {'type': 'Group', 'uuid': str(uuid.uuid3(uuid.NAMESPACE_DNS, `time.time()`))}
            _matrix = _transform.transformation().asMatrix()
            if _matrix != om.MMatrix.identity:
               _object['matrix'] = common.Common.MMatrixToArray(_matrix)

            treeParent['children'].append(_object)

            _childCount = _transform.childCount()
            for i in range(_childCount):
                _child = _transform.child(i)
                self.loopFind(_child, _object)
        elif _type == om.MFn.kMesh:
            _uuidGeo = str(uuid.uuid3(uuid.NAMESPACE_DNS, `time.time()`))

            # _object = {'type': 'Mesh', 'geometry': _uuidGeo, 'material': ''}
            # if 'children' not in treeParent:
            #     treeParent['children'] = []
            treeParent['type'] = 'Mesh'
            treeParent['geometry'] = _uuidGeo

            _mesh =  om.MFnMesh(tObject)
            _dagPath = om.MDagPath()
            om.MDagPath.getAPathTo(tObject, _dagPath)
            self.meshFileManager.setDatas(_dagPath)
            # print _dagPath.fullPathName()
            if _mesh.hasUniqueName():
                _afName = _mesh.name()
            else:
                _afName = _dagPath.fullPathName().replace('|', '_')[1:]
            treeParent['name'] = _afName
            _afPath = '%s.mesh'%_afName
            _projectFolder = os.path.dirname(self.projectPath) # This is folder for project file
            _meshFolder = _projectFolder + '/meshes/' # This is folder for mesh file
            # Create non-existent folders
            if not os.path.isdir(_meshFolder):
                os.makedirs(_meshFolder)

            # Save a .mesh file
            self.meshFileManager.write(_meshFolder + _afPath)
            self.meshFileManager.init()

            self.geometries.append({'uuid': _uuidGeo, 'url': './meshes/' + _afPath});

            _numInstances = _mesh.parentCount()
            _materials = []
            for i in range(_numInstances):
                _shaders = om.MObjectArray()
                _faceIndices = om.MIntArray()
                _mesh.getConnectedShaders(i, _shaders, _faceIndices)
                for j in range(_shaders.length()):
                    _connections = om.MPlugArray()
                    _shaderGroup = om.MFnDependencyNode(_shaders[j])
                    _shaderPlug = _shaderGroup.findPlug("surfaceShader")
                    _shaderPlug.connectedTo(_connections, True, False)

                    for k in range(_connections.length()):
                        _materials.append(_connections[k].node())
            if len(_materials) == 1:
                _material = _materials[0]
                _materialName = om.MFnDependencyNode(_material).name()
                if _materialName not in self.materialName2UUID:
                    _uuidMat = str(uuid.uuid3(uuid.NAMESPACE_DNS, `time.time()`))
                    treeParent['material'] = _uuidMat
                    self.materialName2UUID[_materialName] = _uuidMat
                    _pMaterial = pm.PyNode(_materialName);
                    _materialObject = {
                        'uuid': _uuidMat, 
                        'type': 'MeshLambertMaterial',
                        'color': list(_pMaterial.getAttr('color')),
                        'emissive': list(_pMaterial.getAttr('incandescence'))
                    }

                    self.materials.append(_materialObject)

                    self.intoTexture(_projectFolder + '/textures/', _materialObject, _pMaterial, 'color', 'map')
                    self.intoTexture(_projectFolder + '/textures/', _materialObject, _pMaterial, 'incandescence', 'emissiveMap')
                    self.intoTexture(_projectFolder + '/textures/', _materialObject, _pMaterial, 'normalCamera', 'bumpMap')

                    # _inputs = _pMaterial.inputs()

                    # for _input in _inputs:
                    #     if _input.type() == 'file':
                    #         _textureUrl = _input.getAttr('fileTextureName')
                    #         if os.path.isfile(_textureUrl):
                    #             if _input not in self.textureName2UUID:
                    #                 _textureFolder = _projectFolder + '/textures/'
                    #                 if not os.path.isdir(_textureFolder):
                    #                     os.makedirs(_textureFolder)
                    #                 shutil.copy(_textureUrl, _textureFolder)
                    #                 _uuidTex = str(uuid.uuid3(uuid.NAMESPACE_DNS, `time.time()`))
                    #                 self.textureName2UUID[_input] = _uuidTex
                    #                 # print ;
                    #                 _textureObject = {
                    #                    'uuid': _uuidTex, 
                    #                    'url': './textures/' + os.path.basename(_textureUrl)
                    #                 }

                    #                 self.textures.append(_textureObject)
                    #             else:
                    #                 _materialObject['map'] = self.textureName2UUID[_input]
                else:
                    treeParent['material'] = self.materialName2UUID[_materialName]
                
            # treeParent['children'].append(_object)


    '''输出保存project文件'''           
    def writeProject(self, url, isPutty = True):
        extraTypeNames = ['textManip2D', 'xformManip', 'translateManip', 'cubeManip']
        extraNames = ['groundPlane_transform', 'persp', 'top', 'front', 'side']
        tObjects = []
        dagIterator = om.MItDag(om.MItDag.kBreadthFirst, om.MFn.kInvalid);
        while not dagIterator.isDone():
            dagPath = om.MDagPath()
            dagIterator.getPath(dagPath)
            dagIterator.next() # iterator 跳到下一个
            if dagPath.apiType() == om.MFn.kWorld:
                for i in range(dagPath.childCount()):
                    _child = dagPath.child(i)
                    if _child.hasFn(om.MFn.kTransform):
                        _transform = om.MFnTransform(_child)
                        if _transform.typeName() not in extraTypeNames and _transform.name() not in extraNames:
                            # print _transform.name()
                            tObjects.append(_child)
                break

        self.projectPath = url

        for tObject in tObjects:
            self.loopFind(tObject, self.objectTree)
            # print mTransform.child(0).apiType()
            # 
        _outputTree = {
            'information': {
                'author': 'fun.zheng'
            },
            'geometries': self.geometries,
            'materials': self.materials,
            'textures': self.textures,
            'object': self.objectTree
        }
        if isPutty:
            _outputJson = json.dumps(_outputTree, sort_keys = True, indent = 4, separators = (',', ': '))
        else:
            _outputJson = json.dumps(_outputTree,separators = (',', ':'))

        _f = open(url, 'w')
        try:
            _f.write(_outputJson)
        finally:
            _f.close()
        # print _outputJson
        self.init()

    '''ui part'''
    def ui(self):
        window_name = "MESH_FILE_MANAGER_WINDOW"
        if cmds.window(window_name, ex=True):
            cmds.deleteUI(window_name)
        
        window = cmds.window(window_name, title="Project File Manager", widthHeight=(300, 500))
        cmds.columnLayout(adj=True)
        tabs = cmds.tabLayout()
        import_column = cmds.columnLayout(adj=True)
        cmds.button(label="import mesh", c=self.meshFileManager._import)
        cmds.setParent('..')
        export_column = cmds.columnLayout(adj=True)
        self.uv_cb = cmds.checkBox(label='export uvs', value=True)
        self.normal_cb = cmds.checkBox(label='export normals', value=True)
        cmds.button(label="export all meshes", c=self.meshFileManager._exportAll)
        cmds.button(label="export selected meshes", c=self.meshFileManager._exportSelected)
        cmds.button(label="export project", c=self._exportProject)
        cmds.setParent('..')
        cmds.tabLayout(tabs, edit=True, tabLabel=((import_column, "Import"), (export_column, "Export")))
        cmds.showWindow(window)

    def _exportProject(self, argas):
        # project_paths = self._export("Project (*.project)")
        # if project_paths:
        self.writeProject('/zwf/test/test.project')

    def _export(self, filter = "Mesh (*.mesh)"):
        paths = cmds.fileDialog2(fileFilter=filter, dialogStyle=2)
        self.out_uv = cmds.checkBox(self.uv_cb, q = True, v=True)
        self.out_normal = cmds.checkBox(self.normal_cb, q = True, v=True)
        return paths

def main():
    imExport = ImportAndExport();
    imExport.ui()

if __name__ == '__main__':
    main();