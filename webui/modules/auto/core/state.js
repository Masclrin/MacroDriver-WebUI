'use strict';

export var _s = {
    _nodes: {},
    _nodeList: [],
    _connections: [],
    _linksSparse: [],
    _nextNodeId: 1,
    _nextLinkId: 1,
    _selectedNodeId: null,

    _annotations: [],
    _nextAnnotationId: 1,
    _selectedAnnotationId: null,
    _selectedAnnotations: [],
    _groups: [],
    _nextGroupId: 1,
    _selectedGroupId: null,
    _selectedGroups: [],

    _vpOffset: { x: 100, y: 100 },
    _vpScale: 1,

    _canvasArea: null,
    _viewportEl: null,
    _nodeLayerEl: null,
    _connSvgEl: null,
    _bgEl: null,
    _annotationLayerEl: null,
    _groupLayerEl: null,

    _isPanning: false,
    _panStartX: 0,
    _panStartY: 0,
    _panStartOffX: 0,
    _panStartOffY: 0,

    _isDraggingNode: false,
    _dragNodeId: null,
    _dragOffsetX: 0,
    _dragOffsetY: 0,

    _isConnecting: false,
    _connFromNodeId: null,
    _connFromPortKey: null,
    _connFromDir: null,
    _connFromPortType: null,
    _tmpPathEl: null,

    _spaceHeld: false,

    _isSelecting: false,
    _selStartX: 0,
    _selStartY: 0,
    _selOffX: 0,
    _selOffY: 0,
    _selectedNodes: [],
    _dragStartPositions: {},
    _dragIsMultiSelect: false,
    _dragRAF: 0,
    _dragPendingDx: 0,
    _dragPendingDy: 0,
    _dragGhostEl: null,
    _dragGhostStartLocal: null,
    _dragNearbyAnnotations: [],

    _autoPanRAF: 0,
    _autoPanMouseX: 0,
    _autoPanMouseY: 0,
    _autoPanActive: false,

    _lineDeleteMode: false,
    _lineDeleteDragging: false,

    _onNodeSelected: null,
    _onNodeDeselected: null,
    _onNodeAdded: null,
    _onNodeRemoved: null,
    _onConnectionChange: null
};
