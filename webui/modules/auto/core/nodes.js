'use strict';

import { _portNameMap } from './constants.js';

var _catNames = { action:'动作节点', detection:'检测节点', control:'控制节点', script_block:'动作块', monitor:'监视器', variable:'变量', preset:'预设', utility:'工具', flow:'流程', plugin:'插件' };
var _catColors = { action:'#22c55e', detection:'#eab308', control:'#a855f7', script_block:'#3b82f6', monitor:'#06b6d4', variable:'#f97316', preset:'#f472b6', utility:'#d8d8d8ff', flow:'#ff0000ff', plugin:'#a855f7' };

var _pinyinMap = {
        'flow/start': 'kaishi start',
        'flow/end': 'jieshu end',
        'action/mouse_click': 'shubiao dianji',
        'action/key_action': 'anjian anxia tanchang',
        'action/text_input': 'wenben shuru',
        'action/wait': 'dengdai',
        'action/program_open': 'chengxu dakai qidong',
        'action/program_close': 'chengxu guanbi',
        'action/window_manage': 'chuangkou guanli yidong',
        'action/mouse_scroll': 'gunping gunlun',
        'action/mouse_move': 'shubiao yidong',
        'action/mouse_move_rel': 'xiangdui weiyi shubiao',
        'detection/capture_source': 'jietu jieping yuan capture',
        'detection/check_color': 'yanse jiance',
        'detection/check_ocr': 'OCR shibie wenzi',
        'detection/check_digits': 'shuzi pipei moban shipie',
        'detection/check_image': 'tupian pipei moni',
        'detection/check_screen': 'pingmu zhuangtai jiance',
        'control/if_else': 'ruguo panduan tiaojian',
        'control/loop_count': 'jishu xunhuan',
        'control/loop_while': 'tiaojian xunhuan',
        'control/wait_cond': 'dengdai tiaojian',
        'control/goto': 'tiaozhuan',
        'control/fork': 'bingfa bingxing zhixing',
        'control/join': 'dengdai hehe',
        'control/race': 'jingzheng zhixing',
        'control/race_win': 'jingzheng shengchu',
        'control/stop_branch': 'tingzhi fenzhi',
        'control/pause_branch': 'zanting fenzhi',
        'control/resume_branch': 'huifu fenzhi',
        'control/seq_check': 'shunxu jiance',
        'control/state_machine': 'zhuangtaiji',
        'monitor/monitor_color': 'yanse jianshi',
        'monitor/monitor_ocr': 'OCR jianshi',
        'monitor/monitor_timer': 'dingshiqi jianshi',
        'monitor/monitor_time': 'shijian jianshi time',
        'variable/var_math': 'bianliang shuxue jisuan',
        'variable/var_string': 'zifuchuan caozuo',
        'variable/var_set': 'shezhi bianliang set',
        'variable/var_convert': 'leixing zhuanhuan convert',
        'variable/var_compare': 'bianliang bijiao',
        'variable/var_random': 'suiji suijishu',
        'preset/preset_click': 'dianji zuobiao',
        'preset/preset_find_click': 'zhaotu dianji',
        'preset/preset_read_text': 'zhaotu dqu wenben',
        'script_block/flow_control': 'dongzuo kongzhi flow control stop pause resume',
        'script_block/exec_sub_script': 'zhixing zijiaoben qiantao',
        'script_block/call_script_sync': 'diaoyong hong tongbu',
        'script_block/call_script_async': 'diaoyong hong yibu',
        'utility/string_op': 'zifuchuan chuli',
        'utility/math_func': 'shuxue hanshu',
        'utility/math_op': 'shuxue yunsuan math',
        'utility/const_number': 'shuzi changliang',
        'utility/const_string': 'zifuchuan changliang',
        'utility/const_bool': 'buer changliang bool',
        'utility/compare': 'shuzhi bijiao compare',
        'utility/condition': 'tiaojian xuanze condition',
        'utility/delay': 'yanchi delay',
        'utility/logic_op': 'luoji yunsuan',
        'utility/bookmark': 'zuobiao shuqian',
    };

    function _toZh(name) {
        return _portNameMap[name] || name;
    }

    window.AutomationNodes = {
        _nodeDefs: {},
        _categories: {},
        _pinyinMap: _pinyinMap,

        init: function(callback) {
            var self = this;
            if (window.pywebview && window.pywebview.api && window.pywebview.api.get_node_definitions) {
                window.pywebview.api.get_node_definitions().then(function(resp) {
                    if (resp && resp.ok && resp.data) {
                        self._registerFromPayload(resp.data);
                    } else {
                        self._registerFallback();
                    }
                    if (callback) callback();
                }).catch(function() {
                    self._registerFallback();
                    if (callback) callback();
                });
            } else {
                self._registerFallback();
                if (callback) callback();
            }
        },

        _registerFromPayload: function(payload) {
            var nodes = payload.nodes || {};
            for (var type in nodes) {
                if (!nodes.hasOwnProperty(type)) continue;
                var def = nodes[type];
                if (this._nodeDefs[type] && this._nodeDefs[type].onExecute) {
                    continue;
                }
                this._processAndRegisterNodeDef(type, def);
            }
        },

        _processAndRegisterNodeDef: function(type, def) {
            this._normalizeSchema(def);
            if (def.dynamic_branches) {
                this._expandDynamicBranches(def);
                this._normalizeSchema(def);
            }
            this._nodeDefs[type] = def;
            var cat = def.category || 'other';
            if (!this._categories[cat]) {
                this._categories[cat] = { name: _catNames[cat] || cat, color: _catColors[cat] || def.color || '#888', nodes: [] };
            }
            var exists = false;
            for (var i = 0; i < this._categories[cat].nodes.length; i++) {
                if (this._categories[cat].nodes[i].type === type) { exists = true; break; }
            }
            if (!exists) {
                this._categories[cat].nodes.push({ type: type, name: def.display_name, icon: def.icon || '' });
            }
        },

        _normalizeSchema: function(def) {
            var schema = def.params_schema;
            if (!schema) return;
            var hasCoordMode = false;
            for (var key in schema) {
                if (!schema.hasOwnProperty(key)) continue;
                var s = schema[key];
                if (s.type === 'boolean') s.type = 'bool';
                if (s.format === 'color' && s.type === 'string') s.type = 'color';
                if (s.format === 'region' && (s.type === 'array' || s.type === 'string')) s.type = 'region';
                if (s.format === 'path' && s.type === 'string') { s.type = 'path'; s.browseType = s.browseType || 'template'; }
                if (s.enum && !s.options) {
                    s.options = s.enum;
                }
                if (s.type === 'string' && s.enum) {
                    s.type = 'enum';
                }
                if (s.showWhen && typeof s.showWhen === 'string') {
                    s.showWhen = s.showWhen.replace(/=True/g, '=true').replace(/=False/g, '=false');
                }
                if (s.description && !s.label) {
                    s.label = s.description;
                }
                if (s.description && !s.desc) {
                    s.desc = s.description;
                }
                if (key === 'mode' && s.type === 'enum' && s.options) {
                    var opts = s.options;
                    if (opts.indexOf('screen') >= 0 && opts.indexOf('window') >= 0) {
                        s.coordMode = true;
                        hasCoordMode = true;
                    }
                }
                if (key === 'rect' && s.type === 'region') {
                    s.coordMode = true;
                    s.varRef = true;
                }
                if (key === 'region' && s.type === 'region') {
                    if (hasCoordMode) s.coordMode = true;
                    s.varRef = true;
                }
                if (key === 'hwnd_var') {
                    s.varRef = true;
                    if (hasCoordMode) s.coordMode = true;
                }
                if (key === 'tolerance' || key === 'threshold' || key === 'change_threshold' ||
                    key === 'area_ratio_threshold' || key === 'pyramid_levels') {
                    s.varRef = true;
                }
                if (key === 'store_var') {
                    s.varRef = true;
                }
                if (key === 'input_var') {
                    s.varRef = true;
                }
                if (key === 'counter_var') {
                    s.varRef = true;
                }
                if (key === 'store_hwnd_var') {
                    s.varRef = true;
                }
                if (key === 'store_text_var') {
                    s.varRef = true;
                }
                if (key === 'store_path_var') {
                    s.varRef = true;
                }
                if (key === 'store_number') {
                    s.varRef = true;
                }
                if (key === 'target_color' && s.type === 'color') {
                    s.varRef = true;
                }
                if (s.type === 'path') {
                    s.varRef = true;
                }
                if (key === 'template_path' && s.type === 'path') {
                    s.browseType = 'template';
                }
                if (s.nodeRef && !s._nodeRefProcessed) {
                    s._nodeRefProcessed = true;
                }
                if (s.varRef !== undefined && s.varRef !== null) {
                    s.varRef = !!s.varRef;
                }
            }
            if (def.outputs) {
                for (var i = 0; i < def.outputs.length; i++) {
                    var out = def.outputs[i];
                    if (out.type === 'data_bool') out.type = 'boolean';
                    if (out.type === 'data_number') out.type = 'number';
                    if (out.type === 'data_string') out.type = 'string';
                }
            }
            if (def.inputs) {
                for (var j = 0; j < def.inputs.length; j++) {
                    var inp = def.inputs[j];
                    if (inp.type === 'data_bool') inp.type = 'boolean';
                    if (inp.type === 'data_number') inp.type = 'number';
                    if (inp.type === 'data_string') inp.type = 'string';
                }
            }
        },

        _expandDynamicBranches: function(def) {
            var maxCount = 8;
            if (def.type === 'control/join') {
                def.inputs = [];
                for (var i = 1; i <= maxCount; i++) {
                    def.inputs.push({name: 'branch' + i, type: 'flow'});
                }
            } else {
                var staticOutputs = [];
                for (var j = 0; j < def.outputs.length; j++) {
                    if (def.outputs[j].name !== 'branch1' && def.outputs[j].name !== 'branch2') {
                        staticOutputs.push(def.outputs[j]);
                    }
                }
                def.outputs = staticOutputs;
                for (var i = 1; i <= maxCount; i++) {
                    def.outputs.push({name: 'branch' + i, type: 'flow'});
                }
            }
            var schema = def.params_schema;
            for (var i = 3; i <= maxCount; i++) {
                if (schema.branch_name_1 !== undefined && !schema['branch_name_' + i]) {
                    schema['branch_name_' + i] = {
                        type: 'string', default: '',
                        description: '分支' + i + '名称(空=默认)',
                        showWhen: 'branch_count>=' + i,
                        _branchIndex: i
                    };
                }
                if (schema.branch_affinity_1 !== undefined) {
                    schema['branch_affinity_' + i] = {
                        type: 'affinity', default: {enabled: false, core: -1},
                        description: '分支' + i + '绑核设置',
                        showWhen: 'branch_count>=' + i,
                        _branchIndex: i
                    };
                }
                if (schema.branch_required_1 !== undefined && !schema['branch_required_' + i]) {
                    schema['branch_required_' + i] = {
                        type: 'boolean', default: true,
                        description: '分支' + i + '必须到达',
                        showWhen: 'wait_mode=custom,branch_count>=' + i,
                        _branchIndex: i
                    };
                }
            }
            if (schema.branch_affinity_1 !== undefined) {
                schema.branch_affinity_1._branchIndex = 1;
            }
            if (schema.branch_affinity_2 !== undefined) {
                schema.branch_affinity_2._branchIndex = 2;
            }
            if (schema.branch_required_1 !== undefined) {
                schema.branch_required_1._branchIndex = 1;
            }
            if (schema.branch_required_2 !== undefined) {
                schema.branch_required_2._branchIndex = 2;
            }
        },

        _registerFallback: function() {
            var fallbackDefs = {
                'action/mouse_click': { display_name: '鼠标点击', color: '#22c55e', category: 'action', icon: 'fa-solid fa-arrow-pointer',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { mode:{type:'enum',label:'坐标模式',default:'screen',options:['screen','window','relative','current'],display_names:{'screen':'屏幕坐标','window':'窗口坐标','relative':'相对坐标(0~1)','current':'当前位置'}},
                        x:{type:'number',label:'X坐标(像素)',default:0,coordRef:true,varRef:true,showWhen:'mode=screen,mode=window,mode=relative'}, y:{type:'number',label:'Y坐标(像素)',default:0,coordRef:true,varRef:true,showWhen:'mode=screen,mode=window,mode=relative'},
                        hwnd_var:{type:'string',label:'窗口句柄变量名',default:'',varRef:true,showWhen:'mode=window,mode=relative'},
                        button:{type:'enum',label:'鼠标按键',default:'left',options:['left','right','middle'],display_names:{'left':'左键','right':'右键','middle':'中键'}},
                        click_type:{type:'enum',label:'点击方式',default:'click',options:['click','dblclick','press','release','long_press'],display_names:{'click':'单击','dblclick':'双击','press':'按住','release':'松开','long_press':'长按'}},
                        hold_time:{type:'number',label:'长按时长',default:0,varRef:true}, move_duration:{type:'number',label:'移动耗时',default:0,varRef:true,showWhen:'mode=screen,mode=window,mode=relative'},
                        before_delay:{type:'number',label:'前延迟',default:0,varRef:true}, after_delay:{type:'number',label:'后延迟',default:0,varRef:true},
                        store_hwnd_var:{type:'string',label:'存入窗口句柄',default:'',varRef:true,showWhen:'mode=window,mode=relative'} }},
                'action/key_action': { display_name: '按键动作', color: '#22c55e', category: 'action', icon: 'fa-solid fa-keyboard',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { action:{type:'enum',label:'按键动作',default:'click',options:['click','press','release','type'],display_names:{'click':'单击','press':'按住','release':'松开','type':'连续输入'}},
                        key:{type:'string',label:'按键',default:'',varRef:true,keySelector:true}, delay:{type:'number',label:'后延迟',default:0,varRef:true},
                        text_input_delay:{type:'number',label:'字符间隔(ms)',default:10,showWhen:'action=type',varRef:true} }},
                'action/mouse_scroll': { display_name: '鼠标滚轮', color: '#22c55e', category: 'action', icon: 'fa-solid fa-arrows-up-down',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { delta:{type:'number',label:'滚动量（120为一个单位，+上 -下）',default:120,varRef:true}, delay:{type:'number',label:'后延迟',default:0,varRef:true} }},
                'action/text_input': { display_name: '文本输入', color: '#22c55e', category: 'action', icon: 'fa-solid fa-font',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { text:{type:'string',label:'文本内容',default:'',varRef:true,multiline:true}, interval:{type:'number',label:'字符间隔',default:50,varRef:true},
                        before_delay:{type:'number',label:'前延迟',default:0,varRef:true} }},
                'action/wait': { display_name: '等待', color: '#22c55e', category: 'action', icon: 'fa-solid fa-clock',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { mode:{type:'enum',label:'等待模式',default:'duration',options:['duration','until_time'],display_names:{'duration':'固定时长','until_time':'等到指定时间'}},
                        duration:{type:'number',label:'等待时长(ms)',default:0,varRef:true,showWhen:'mode=duration'},
                        unit:{type:'enum',label:'时间单位',default:'ms',options:['ms','s','min'],display_names:{'ms':'毫秒(ms)','s':'秒(s)','min':'分钟(min)'},showWhen:'mode=duration'},
                        hour:{type:'number',label:'目标小时',default:8,showWhen:'mode=until_time',varRef:true},
                        minute:{type:'number',label:'目标分钟',default:0,showWhen:'mode=until_time',varRef:true},
                        second:{type:'number',label:'目标秒',default:0,showWhen:'mode=until_time',varRef:true},
                        next_day:{type:'bool',label:'已过则等次日',default:false,showWhen:'mode=until_time'} }},
                'action/window_manage': { display_name: '窗口管理', color: '#22c55e', category: 'action', icon: 'fa-solid fa-window-restore',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { find_mode:{type:'enum',label:'查找方式',default:'title',options:['title','hwnd','hwnd_var'],display_names:{'title':'按标题','hwnd':'按句柄 hwnd','hwnd_var':'按句柄变量'}},
                        title:{type:'string',label:'窗口标题(支持模糊匹配)',default:'',showWhen:'find_mode=title',varRef:true,windowPicker:true},
                        hwnd_value:{type:'string',label:'窗口句柄',default:'',showWhen:'find_mode=hwnd',varRef:true},
                        hwnd_var:{type:'string',label:'窗口句柄变量名',default:'',showWhen:'find_mode=hwnd_var',varRef:true},
                        action:{type:'enum',label:'窗口操作',default:'activate',options:['activate','maximize','minimize','restore','close','move_to_monitor'],display_names:{'activate':'激活(置顶)','maximize':'最大化','minimize':'最小化','restore':'还原','close':'关闭','move_to_monitor':'移至显示器'}},
                        monitor_index:{type:'number',label:'显示器序号',default:0,showWhen:'action=move_to_monitor',varRef:true},
                        store_hwnd_var:{type:'string',label:'存储句柄变量',default:''} }},
                'action/program_open': { display_name: '打开程序', color: '#22c55e', category: 'action', icon: 'fa-solid fa-play',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { path:{type:'string',label:'程序路径',default:'',varRef:true,browseType:'program'},
                        args:{type:'string',label:'启动参数',default:'',varRef:true},
                        work_dir:{type:'string',label:'工作目录',default:'',varRef:true},
                        wait_start:{type:'number',label:'启动后等待(ms)',default:0,varRef:true},
                        store_hwnd_var:{type:'string',label:'存储句柄变量',default:''} }},
                'action/program_close': { display_name: '关闭程序', color: '#22c55e', category: 'action', icon: 'fa-solid fa-xmark',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { close_mode:{type:'enum',label:'关闭方式',default:'name',options:['name','pid','hwnd','hwnd_var'],display_names:{'name':'按进程名','pid':'按PID','hwnd':'按句柄','hwnd_var':'按变量'}},
                        process_name:{type:'string',label:'进程名',default:'',showWhen:'close_mode=name',varRef:true,processPicker:true},
                        pid_value:{type:'string',label:'进程PID',default:'',showWhen:'close_mode=pid',varRef:true},
                        hwnd_value:{type:'string',label:'窗口句柄',default:'',showWhen:'close_mode=hwnd',varRef:true},
                        hwnd_var:{type:'string',label:'窗口变量',default:'',showWhen:'close_mode=hwnd_var',varRef:true},
                        force:{type:'bool',label:'强制终止',default:false} }},
                'detection/capture_source': { display_name: '截图源', color: '#eab308', category: 'detection', icon: 'fa-solid fa-camera',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { enabled:{type:'bool',label:'启用后台截图',default:true},
                        fps:{type:'number',label:'采集帧率(1-360)',default:60,varRef:true},
                        monitor_index:{type:'number',label:'目标显示器索引(0=主屏,1=副屏...)',default:0} }},
                'detection/check_color': { display_name: '颜色检测', color: '#eab308', category: 'detection', icon: 'fa-solid fa-palette',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'match',type:'flow'},{name:'no',type:'flow'},{name:'result',type:'boolean'},{name:'color',type:'string'}],
                    params_schema: { mode:{type:'enum',label:'坐标模式',default:'screen',options:['screen','window','relative'],coordMode:true,display_names:{'screen':'屏幕坐标','window':'窗口坐标','relative':'相对坐标(0~1)'}},
                        rect:{type:'region',label:'检测区域[x,y,w,h]',default:[0,0,10,10],coordMode:true,varRef:true}, hwnd_var:{type:'string',label:'窗口句柄变量名',default:'',varRef:true,showWhen:'mode=window,mode=relative'},
                        target_color:{type:'color',label:'目标颜色(点击选色)',default:'#FF0000',varRef:true,showWhen:'check_mode!=change'}, tolerance:{type:'number',label:'容差(0-255)',default:10,varRef:true,showWhen:'check_mode!=change'},
                        check_mode:{type:'enum',label:'检测模式',default:'contain',options:['exact','contain','change','area'],display_names:{'exact':'精确匹配(全等)','contain':'包含匹配(有即可)','change':'变化检测(帧间差异)','area':'面积占比(比例阈值)'}},
                        change_threshold:{type:'number',label:'变化阈值',default:10,showWhen:'check_mode=change',varRef:true},
                        area_ratio_threshold:{type:'number',label:'面积占比阈值(0-1)',default:0.5,showWhen:'check_mode=area',varRef:true,step:'0.01'},
                        sample_mode:{type:'enum',label:'采样模式',default:'center',options:['center','mean','max_diff'],display_names:{'center':'中心点采样','mean':'平均色采样','max_diff':'最大差异采样'},showWhen:'check_mode=contain'},
                        store_var:{type:'string',label:'存入变量',default:''},
                        wait:{type:'bool',label:'持续等待',default:false},
                        wait_interval_ms:{type:'number',label:'轮询间隔(ms)',default:16,showWhen:'wait=true',varRef:true},
                        wait_timeout_ms:{type:'number',label:'等待超时(ms)',default:5000,showWhen:'wait=true',varRef:true} }},
                'detection/check_ocr': { display_name: 'OCR识别', color: '#eab308', category: 'detection', icon: 'fa-solid fa-language',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'match',type:'flow'},{name:'no',type:'flow'},{name:'result',type:'boolean'},{name:'text',type:'string'},{name:'number',type:'number'}],
                    params_schema: { mode:{type:'enum',label:'坐标模式',default:'screen',options:['screen','window','relative'],coordMode:true,display_names:{'screen':'屏幕坐标','window':'窗口坐标','relative':'相对坐标(0~1)'}},
                        rect:{type:'region',label:'检测区域[x,y,w,h]',default:[0,0,100,30],coordMode:true}, hwnd_var:{type:'string',label:'窗口句柄变量名',default:'',varRef:true,showWhen:'mode=window,mode=relative'},
                        match_text:{type:'string',label:'匹配文本(留空=仅识别)',default:'',varRef:true},
                        match_mode:{type:'enum',label:'匹配模式',default:'contain',options:['contain','exact','regex','number_gt','number_lt','number_eq'],display_names:{'contain':'包含(模糊)','exact':'完全匹配(精确)','regex':'正则表达式','number_gt':'数值大于','number_lt':'数值小于','number_eq':'数值等于'}},
                        match_number:{type:'number',label:'比较数值',default:0,varRef:true,showWhen:'match_mode=number_gt,number_lt,number_eq'},
                        store_var:{type:'string',label:'存入文本变量(新建/覆盖)',default:''},
                        store_number:{type:'string',label:'存入数字变量',default:'',showWhen:'match_mode=number_gt,number_lt,number_eq',varRef:true},
                        cache_strategy:{type:'enum',label:'缓存策略',default:'time_interval',options:['frame_diff','time_interval','disabled'],display_names:{'frame_diff':'帧差分(高灵敏度)','time_interval':'时间间隔(低占用)','disabled':'不缓存(实时)'}},
                        cache_interval_ms:{type:'number',label:'缓存间隔',default:100,showWhen:'cache_strategy=time_interval',varRef:true},
                        wait:{type:'bool',label:'持续等待',default:false},
                        wait_interval_ms:{type:'number',label:'轮询间隔(ms)',default:16,showWhen:'wait=true',varRef:true},
                        wait_timeout_ms:{type:'number',label:'等待超时(ms)',default:5000,showWhen:'wait=true',varRef:true},
                        ocr_engine:{type:'enum',label:'OCR引擎',default:'rapidocr_onnx',options:['rapidocr_onnx'],display_names:{'rapidocr_onnx':'RapidOCR (ONNX)'}},
                        ocr_preload:{type:'bool',label:'启动时预加载OCR模型(避免首次卡顿)',default:true},
                        ocr_affinity_core:{type:'number',label:'OCR专用核心号(-1=不绑核)',default:-1,showWhen:'ocr_preload=true'} }},
                'detection/check_digits': { display_name: '数字匹配', color: '#eab308', category: 'detection', icon: 'fa-solid fa-hashtag',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'pass',type:'flow'},{name:'fail',type:'flow'},{name:'digit_value',type:'number'},{name:'match_conf',type:'number'}],
                    params_schema: {
                        mode:{type:'enum',label:'坐标模式',default:'screen',options:['screen','window','relative'],coordMode:true,display_names:{'screen':'屏幕坐标','window':'窗口坐标','relative':'相对坐标(0~1)'}},
                        rect:{type:'region',label:'数字区域[x,y,w,h]',default:[0,0,0,0],coordMode:true,varRef:true}, hwnd_var:{type:'string',label:'窗口句柄变量名',default:'',varRef:true,showWhen:'mode=window,mode=relative'},
                        template_folder:{type:'path',label:'模板根目录',default:'',browseType:'folder',varRef:true},
                        template_sets:{type:'string',label:'使用模板集(逗号分隔,留空=全部)',default:'',varRef:true},
                        match_method:{type:'enum',label:'匹配方法',default:'auto',options:['auto','hamming','template_match'],display_names:{'auto':'自动','hamming':'汉明距离(二值图,自缩放ROI)','template_match':'模板匹配(滑动窗口,兼容好)'}},
                        binary_method:{type:'enum',label:'二值化方法',default:'otsu',options:['otsu','adaptive_gaussian'],display_names:{'otsu':'OTSU(速度快)','adaptive_gaussian':'自适应高斯(抗渐变)'}},
                        threshold:{type:'number',label:'匹配置信度(0-1)',default:0.8,min:0,max:1,varRef:true},
                        split_method:{type:'enum',label:'数字分割方式',default:'contour',options:['contour','projection','fixed_width'],display_names:{'contour':'轮廓分割(自动)','projection':'投影分割(抗噪)','fixed_width':'等宽分割(对位)'}},
                        split_width:{type:'number',label:'分割参数(px)',default:0,min:0,varRef:true,descMapCond:'split_method',descMap:{'projection':'最小字符宽度(px)，过滤窄噪点如冒号','fixed_width':'每个数字的精确宽度(px)'},desc:'0=自动',showWhen:'split_method=fixed_width,split_method=projection'},
                        compare_op:{type:'enum',label:'数值比较',default:'none',options:['none','eq','ne','gt','gte','lt','lte'],display_names:{'none':'不比较(仅识别)','eq':'= 等于','ne':'≠ 不等于','gt':'> 大于','gte':'≥ 大于等于','lt':'< 小于','lte':'≤ 小于等于'}},
                        compare_value:{type:'number',label:'比较目标值',default:0,varRef:true,showWhen:'compare_op=eq,compare_op=ne,compare_op=gt,compare_op=gte,compare_op=lt,compare_op=lte'},
                        store_var:{type:'string',label:'存入变量',default:'',varRef:true},
                        wait:{type:'bool',label:'持续等待',default:false},
                        wait_interval_ms:{type:'number',label:'轮询间隔(ms)',default:50,showWhen:'wait=true',varRef:true},
                        wait_timeout_ms:{type:'number',label:'等待超时(ms)',default:5000,showWhen:'wait=true',varRef:true} }},
                'control/if_else': { display_name: '条件分支', color: '#a855f7', category: 'control', icon: 'fa-solid fa-code-branch',
                    inputs: [{name:'in',type:'flow'},{name:'cond',type:'boolean'}],
                    outputs: [{name:'true',type:'flow'},{name:'false',type:'flow'}],
                    params_schema: { logic:{type:'enum',label:'逻辑组合(多条件时)',default:'AND',options:['AND','OR','NOT'],display_names:{'AND':'与(全部满足)','OR':'或(任一满足)','NOT':'非(取反)'}},
                        fallback:{type:'enum',label:'无数据连接时默认走向',default:'false',options:['true','false'],display_names:{'true':'走\'是\'分支','false':'走\'否\'分支'}} }},
                'control/loop_count': { display_name: '计数循环', color: '#a855f7', category: 'control', icon: 'fa-solid fa-repeat',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'body',type:'flow'},{name:'next',type:'flow'}],
                    params_schema: { count:{type:'number',label:'循环次数',default:1,varRef:true}, counter_var:{type:'string',label:'计数器变量',default:''} }},
                'control/loop_while': { display_name: '条件循环', color: '#a855f7', category: 'control', icon: 'fa-solid fa-rotate',
                    inputs: [{name:'in',type:'flow'},{name:'cond',type:'boolean'}],
                    outputs: [{name:'body',type:'flow'},{name:'next',type:'flow'}],
                    params_schema: { max_iterations:{type:'number',label:'最大循环次数(防死循环)',default:10000,varRef:true},
                        check_at:{type:'enum',label:'检查时机',default:'start',options:['start','end'],display_names:{'start':'循环前检查(先判断后执行)','end':'循环后检查(先执行后判断)'}} }},
                'script_block/call_script_sync': { display_name: '调用宏(同步)', color: '#3b82f6', category: 'script_block', icon: 'fa-solid fa-play',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { path:{type:'path',label:'旧JSON宏文件路径(.json)',default:'',varRef:true}, speed_factor:{type:'number',label:'倍速(1.0=原速)',default:1.0},
                        timeline_mode:{type:'enum',label:'时间线模式',default:'absolute',options:['absolute','relative_compensated'],display_names:{'absolute':'绝对时间线(高精度)','relative_compensated':'相对补偿(低占用)'}},
                        random_delay:{type:'bool',label:'启用随机延迟修正(拟人化)',default:false} }},
                'script_block/call_script_async': { display_name: '调用宏(异步)', color: '#3b82f6', category: 'script_block', icon: 'fa-solid fa-forward',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'},{name:'completed',type:'flow'},{name:'interrupted',type:'flow'}],
                    params_schema: { path:{type:'path',label:'旧JSON宏文件路径(.json)',default:'',varRef:true}, speed_factor:{type:'number',label:'倍速(1.0=原速)',default:1.0},
                        timeline_mode:{type:'enum',label:'时间线模式',default:'absolute',options:['absolute','relative_compensated'],display_names:{'absolute':'绝对时间线(高精度)','relative_compensated':'相对补偿(低占用)'}},
                        random_delay:{type:'bool',label:'启用随机延迟修正(拟人化)',default:false} }},
                'monitor/monitor_color': { display_name: '颜色监视', color: '#06b6d4', category: 'monitor', icon: 'fa-solid fa-eye',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'trigger',type:'flow'},{name:'timeout',type:'flow'}],
                    params_schema: { mode:{type:'enum',label:'坐标模式',default:'screen',options:['screen','window','relative'],coordMode:true,display_names:{'screen':'屏幕坐标','window':'窗口坐标','relative':'相对坐标(0~1)'}},
                        rect:{type:'region',label:'检测区域[x,y,w,h]',default:[0,0,10,10],coordMode:true,varRef:true}, hwnd_var:{type:'string',label:'窗口句柄变量名',default:'',varRef:true,showWhen:'mode=window,mode=relative'},
                        target_color:{type:'color',label:'目标颜色(点击选色)',default:'#FF0000',varRef:true,showWhen:'check_mode!=change'}, tolerance:{type:'number',label:'容差(0-255)',default:10,varRef:true,showWhen:'check_mode!=change'},
                        check_mode:{type:'enum',label:'检测模式',default:'contain',options:['contain','change','area'],display_names:{'contain':'包含匹配(有即可)','change':'变化检测(帧间差异)','area':'面积占比(比例阈值)'}},
                        sample_mode:{type:'enum',label:'采样模式',default:'center',options:['center','mean','max_diff'],display_names:{'center':'中心点采样','mean':'平均色采样','max_diff':'最大差异采样'},showWhen:'check_mode=contain'},
                        change_threshold:{type:'number',label:'变化阈值',default:10,showWhen:'check_mode=change',varRef:true},
                        area_ratio_threshold:{type:'number',label:'面积占比阈值(0-1)',default:0.5,showWhen:'check_mode=area',varRef:true},
                        interval:{type:'number',label:'检测间隔(ms)',default:100,varRef:true}, timeout:{type:'number',label:'超时(ms, 0=无限等待)',default:0,varRef:true},
                        trigger_mode:{type:'enum',label:'触发模式',default:'appear',options:['appear','disappear','change','absent'],display_names:{'appear':'出现时触发','disappear':'消失时触发(需先检测到)','change':'变化时触发(有/无翻转)','absent':'不存在即触发(无需先检测到)'}},
                        initial_check:{type:'enum',label:'首帧行为',default:'baseline',options:['baseline','trigger'],display_names:{'baseline':'记录基线(首帧不触发)','trigger':'立即判断(首帧即可能触发)'},showWhen:'trigger_mode=disappear,trigger_mode=change'},
                        on_trigger:{type:'enum',label:'触发后行为',default:'branch',options:['branch','stop_all','stop_task','pause_task','resume_task'],display_names:{'branch':'走trigger分支','stop_all':'停止所有任务','stop_task':'停止指定任务','pause_task':'暂停指定任务','resume_task':'恢复指定任务'}},
                        target_task:{type:'string',label:'目标任务ID',default:'',showWhen:'on_trigger=stop_task,pause_task,resume_task',nodeRef:'script_block/call_script_async,script_block/exec_sub_script',varRef:true},
                        auto_stop:{type:'bool',label:'触发后自动停止',default:true},
                        recheck_delay_ms:{type:'number',label:'再次检测等待(ms)',default:500,showWhen:'auto_stop=false',varRef:true},
                        max_triggers:{type:'number',label:'最大触发次数',default:0,showWhen:'auto_stop=false',varRef:true},
                        auto_close_after_ms:{type:'number',label:'自动关闭超时(ms)',default:0,showWhen:'auto_stop=false',varRef:true} }},
                'monitor/monitor_ocr': { display_name: 'OCR监视', color: '#06b6d4', category: 'monitor', icon: 'fa-solid fa-eye',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'trigger',type:'flow'},{name:'timeout',type:'flow'}],
                    params_schema: { mode:{type:'enum',label:'坐标模式',default:'screen',options:['screen','window','relative'],coordMode:true,display_names:{'screen':'屏幕坐标','window':'窗口坐标','relative':'相对坐标(0~1)'}},
                        rect:{type:'region',label:'检测区域[x,y,w,h]',default:[0,0,100,30],coordMode:true,varRef:true}, hwnd_var:{type:'string',label:'窗口句柄变量名',default:'',varRef:true,showWhen:'mode=window,mode=relative'},
                        match_text:{type:'string',label:'匹配文本(留空=仅识别)',default:'',varRef:true},
                        match_mode:{type:'enum',label:'匹配模式',default:'contain',options:['contain','exact','regex','number_gt','number_lt','number_eq'],display_names:{'contain':'包含(模糊)','exact':'完全匹配(精确)','regex':'正则表达式','number_gt':'数值大于','number_lt':'数值小于','number_eq':'数值等于'}},
                        match_number:{type:'number',label:'比较数值',default:0,varRef:true,showWhen:'match_mode=number_gt,number_lt,number_eq'},
                        cache_strategy:{type:'enum',label:'缓存策略',default:'time_interval',options:['frame_diff','time_interval','disabled'],display_names:{'frame_diff':'帧差分(高灵敏度)','time_interval':'时间间隔(低占用)','disabled':'不缓存(实时)'}},
                        cache_interval_ms:{type:'number',label:'缓存间隔(ms)',default:100,showWhen:'cache_strategy=time_interval',varRef:true},
                        interval:{type:'number',label:'检测间隔(ms)',default:200,varRef:true}, timeout:{type:'number',label:'超时(ms, 0=无限等待)',default:0,varRef:true},
                        trigger_mode:{type:'enum',label:'触发模式',default:'appear',options:['appear','disappear','change','absent'],display_names:{'appear':'出现时触发','disappear':'消失时触发(需先检测到)','change':'变化时触发(有/无翻转)','absent':'不存在即触发(无需先检测到)'}},
                        initial_check:{type:'enum',label:'首帧行为',default:'baseline',options:['baseline','trigger'],display_names:{'baseline':'记录基线(首帧不触发)','trigger':'立即判断(首帧即可能触发)'},showWhen:'trigger_mode=disappear,trigger_mode=change'},
                        on_trigger:{type:'enum',label:'触发后行为',default:'branch',options:['branch','stop_all','stop_task','pause_task','resume_task'],display_names:{'branch':'走trigger分支','stop_all':'停止所有任务','stop_task':'停止指定任务','pause_task':'暂停指定任务','resume_task':'恢复指定任务'}},
                        target_task:{type:'string',label:'目标任务ID',default:'',showWhen:'on_trigger=stop_task,pause_task,resume_task',nodeRef:'script_block/call_script_async,script_block/exec_sub_script',varRef:true},
                        store_var:{type:'string',label:'存入变量',default:'',varRef:true},
                        store_number:{type:'string',label:'数值存入变量',default:'',varRef:true,showWhen:'match_mode=number_gt,number_lt,number_eq'},
                        auto_stop:{type:'bool',label:'触发后自动停止',default:true},
                        recheck_delay_ms:{type:'number',label:'再次检测等待(ms)',default:500,showWhen:'auto_stop=false',varRef:true},
                        max_triggers:{type:'number',label:'最大触发次数',default:0,showWhen:'auto_stop=false',varRef:true},
                        auto_close_after_ms:{type:'number',label:'自动关闭超时(ms)',default:0,showWhen:'auto_stop=false',varRef:true},
                        ocr_engine:{type:'enum',label:'OCR引擎',default:'rapidocr_onnx',options:['rapidocr_onnx'],display_names:{'rapidocr_onnx':'RapidOCR (ONNX)'}},
                        ocr_preload:{type:'bool',label:'启动时预加载OCR模型(避免首次卡顿)',default:true},
                        ocr_affinity_core:{type:'number',label:'OCR专用核心号(-1=不绑核)',default:-1,showWhen:'ocr_preload=true'} }},
                'monitor/monitor_timer': { display_name: '定时器', color: '#06b6d4', category: 'monitor', icon: 'fa-solid fa-stopwatch',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'trigger',type:'flow'},{name:'timeout',type:'flow'}],
                    params_schema: { interval:{type:'number',label:'触发间隔(ms)，1000=每秒一次',default:1000,varRef:true},
                        on_trigger:{type:'enum',label:'触发后行为',default:'branch',options:['branch','stop_all','stop_task','pause_task','resume_task'],display_names:{'branch':'走trigger分支','stop_all':'停止所有任务','stop_task':'停止指定任务','pause_task':'暂停指定任务','resume_task':'恢复指定任务'}},
                        target_task:{type:'string',label:'目标任务ID',default:'',showWhen:'on_trigger=stop_task,pause_task,resume_task',nodeRef:'script_block/call_script_async,script_block/exec_sub_script',varRef:true},
                        auto_stop:{type:'bool',label:'触发后自动停止',default:true},
                        recheck_delay_ms:{type:'number',label:'再次检测等待(ms)',default:500,showWhen:'auto_stop=false',varRef:true},
                        max_triggers:{type:'number',label:'最大触发次数',default:0,showWhen:'auto_stop=false',varRef:true},
                        auto_close_after_ms:{type:'number',label:'自动关闭超时(ms)',default:0,showWhen:'auto_stop=false',varRef:true} }},
                'monitor/monitor_time': { display_name: '时间监视', color: '#06b6d4', category: 'monitor', icon: 'fa-solid fa-bell',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'trigger',type:'flow'},{name:'timeout',type:'flow'}],
                    params_schema: { hour:{type:'number',label:'目标小时',default:8,varRef:true}, minute:{type:'number',label:'目标分钟',default:0,varRef:true},
                        second:{type:'number',label:'目标秒',default:0,varRef:true}, next_day:{type:'bool',label:'已过则等次日',default:false},
                        check_interval:{type:'number',label:'检查间隔(ms)',default:500,varRef:true},
                        timeout:{type:'number',label:'超时(ms)',default:0,varRef:true},
                        on_trigger:{type:'enum',label:'触发行为',default:'branch',options:['branch','stop_all','stop_task','pause_task','resume_task']},
                        target_task:{type:'string',label:'目标任务ID',default:'',showWhen:'on_trigger=stop_task,pause_task,resume_task',nodeRef:'script_block/call_script_async,script_block/exec_sub_script',varRef:true},
                        auto_stop:{type:'bool',label:'触发后自动停止',default:true},
                        recheck_delay_ms:{type:'number',label:'循环重检延迟(ms)',default:500,showWhen:'auto_stop=false',varRef:true},
                        max_triggers:{type:'number',label:'最大触发次数',default:0,showWhen:'auto_stop=false',varRef:true},
                        auto_close_after_ms:{type:'number',label:'自动关闭超时(ms)',default:0,showWhen:'auto_stop=false',varRef:true} }},
                'variable/var_set': { display_name: '设置变量', color: '#f97316', category: 'variable', icon: 'fa-solid fa-equals',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { vars_json:{type:'var_list',label:'变量列表',default:'[]'} }},
                  'variable/var_math': { display_name: '数学运算', color: '#f97316', category: 'variable', icon: 'fa-solid fa-calculator',
                    inputs: [{name:'in',type:'flow'},{name:'A',type:'number'},{name:'B',type:'number'}], outputs: [{name:'next',type:'flow'},{name:'result',type:'number'}],
                    params_schema: { op:{type:'enum',label:'运算类型',default:'+',options:['+','-','*','/','%','^','min','max','abs','round'],display_names:{'+':'加法(+)','-':'减法(-)','*':'乘法(×)','/':'除法(÷)','%':'取余(模)','^':'乘方(幂)','min':'取最小值','max':'取最大值','abs':'绝对值','round':'四舍五入'}},
                        a:{type:'string',label:'操作数A',default:'0',varRef:true}, b:{type:'string',label:'操作数B(round=小数位)',default:'0',varRef:true,showWhen:'op=+,op=-,op=*,op=/,op=%,op=^,op=min,op=max,op=round'}, store_var:{type:'string',label:'存入变量',default:''} }},
                'variable/var_compare': { display_name: '比较', color: '#f97316', category: 'variable', icon: 'fa-solid fa-not-equal',
                    inputs: [{name:'in',type:'flow'},{name:'A',type:'number'},{name:'B',type:'number'}], outputs: [{name:'next',type:'flow'},{name:'result',type:'boolean'}],
                    params_schema: { op:{type:'enum',label:'比较运算',default:'>',options:['>','<','>=','<=','==','!='],display_names:{'>':'大于(>)','<':'小于(<)','>=':'大于等于(≥)','<=':'小于等于(≤)','==':'等于(==)','!=':'不等于(!=)'}},
                        a:{type:'string',label:'值A',default:'0',varRef:true}, b:{type:'string',label:'值B',default:'0',varRef:true} }},
                'variable/var_string': { display_name: '字符串操作', color: '#f97316', category: 'variable', icon: 'fa-solid fa-text-width',
                    inputs: [{name:'in',type:'flow'},{name:'str',type:'string'}], outputs: [{name:'next',type:'flow'},{name:'result',type:'string'}],
                    params_schema: { op:{type:'enum',label:'操作类型',default:'concat',options:['concat','replace','upper','lower','trim','substring','split_index','regex_extract'],display_names:{'concat':'拼接(合并)','replace':'替换(查找替换)','upper':'转大写','lower':'转小写','trim':'去首尾空格','substring':'截取子串','split_index':'分割取段','regex_extract':'正则提取'}},
                        a:{type:'string',label:'输入字符串',default:'',varRef:true},
                        concat_str:{type:'string',label:'拼接字符串',default:'',varRef:true,showWhen:'op=concat'},
                        search_str:{type:'string',label:'查找文本',default:'',varRef:true,showWhen:'op=replace'},
                        replace_str:{type:'string',label:'替换为',default:'',varRef:true,showWhen:'op=replace'},
                        start_pos:{type:'number',label:'起始位置',default:0,showWhen:'op=substring',varRef:true},
                        length:{type:'number',label:'截取长度',default:0,showWhen:'op=substring',varRef:true},
                        delimiter:{type:'string',label:'分隔符(如逗号、竖线)',default:',',varRef:true,showWhen:'op=split_index'},
                        index:{type:'number',label:'取第几段(从0开始)',default:0,showWhen:'op=split_index',varRef:true},
                        regex_pattern:{type:'string',label:'正则表达式(如\\d+匹配数字)',default:'',varRef:true,showWhen:'op=regex_extract'},
                        store_var:{type:'string',label:'存入变量',default:'',varRef:true} }},
                'variable/var_convert': { display_name: '类型转换', color: '#f97316', category: 'variable', icon: 'fa-solid fa-arrow-right-arrow-left',
                    inputs: [{name:'in',type:'flow'},{name:'val',type:'any'}], outputs: [{name:'next',type:'flow'},{name:'result',type:'any'}],
                    params_schema: { to_type:{type:'enum',label:'目标类型',default:'number',options:['number','string','boolean'],display_names:{'number':'数字','string':'文本(字符串)','boolean':'bool(真假)'}},
                        input_var:{type:'string',label:'输入变量',default:'',varRef:true}, store_var:{type:'string',label:'存入变量',default:''} }},
                'variable/var_random': { display_name: '随机数生成', color: '#f97316', category: 'variable', icon: 'fa-solid fa-dice',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'},{name:'result',type:'any'}],
                    params_schema: { mode:{type:'enum',label:'随机模式',default:'number',options:['number','string'],display_names:{'number':'随机数字','string':'随机文本'}},
                        min_val:{type:'number',label:'最小值(含)',default:1,showWhen:'mode=number',varRef:true},
                        max_val:{type:'number',label:'最大值(含)',default:100,showWhen:'mode=number',varRef:true},
                        int_only:{type:'bool',label:'仅整数',default:true,showWhen:'mode=number'},
                        charset:{type:'enum',label:'字符集',default:'alpha',options:['alpha','alphanumeric','numeric','custom'],showWhen:'mode=string',display_names:{'alpha':'字母(a-Z)','alphanumeric':'字母+数字','numeric':'纯数字','custom':'自定义'}},
                        custom_chars:{type:'string',label:'自定义字符池',default:'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',showWhen:'mode=string,charset=custom',varRef:true},
                        length:{type:'number',label:'字符串长度',default:8,showWhen:'mode=string',varRef:true},
                        store_var:{type:'string',label:'存入变量',default:'',varRef:true} }},
                'action/mouse_move': { display_name: '鼠标移动', color: '#22c55e', category: 'action', icon: 'fa-solid fa-up-down-left-right',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { mode:{type:'enum',label:'坐标模式',default:'screen',options:['screen','window','relative'],display_names:{'screen':'屏幕坐标','window':'窗口坐标','relative':'相对坐标(0~1)'}},
                        x:{type:'number',label:'X坐标(像素)',default:0,coordRef:true,varRef:true,showWhen:'mode=screen,mode=window,mode=relative'}, y:{type:'number',label:'Y坐标(像素)',default:0,coordRef:true,varRef:true,showWhen:'mode=screen,mode=window,mode=relative'},
                        hwnd_var:{type:'string',label:'窗口句柄变量名',default:'',varRef:true,showWhen:'mode=window,mode=relative'},
                        duration:{type:'number',label:'移动耗时(ms)',default:200,varRef:true},
                        easing:{type:'enum',label:'缓动效果',default:'ease_in_out',options:['linear','ease_in_out','ease_in','ease_out'],display_names:{'linear':'线性(匀速)','ease_in_out':'缓入缓出(自然)','ease_in':'缓入(由慢到快)','ease_out':'缓出(由快到慢)'}} }},
                'action/mouse_move_rel': { display_name: '相对位移', color: '#22c55e', category: 'action', icon: 'fa-solid fa-arrows-up-down-left-right',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { dx:{type:'number',label:'DX',default:0,varRef:true}, dy:{type:'number',label:'DY',default:0,varRef:true},
                        duration:{type:'number',label:'移动耗时',default:200,varRef:true} }},
                'detection/check_image': { display_name: '图像匹配', color: '#eab308', category: 'detection', icon: 'fa-solid fa-image',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'match',type:'flow'},{name:'no',type:'flow'},{name:'result',type:'boolean'},{name:'match_x',type:'number'},{name:'match_y',type:'number'},{name:'confidence',type:'number'}],
                    params_schema: { mode:{type:'enum',label:'坐标模式',default:'screen',options:['screen','window','relative'],coordMode:true,display_names:{'screen':'屏幕坐标','window':'窗口坐标','relative':'相对坐标(0~1)'}},
                        rect:{type:'region',label:'搜索区域(全零=全屏)',default:[0,0,0,0],coordMode:true,varRef:true}, hwnd_var:{type:'string',label:'窗口句柄变量名',default:'',varRef:true,showWhen:'mode=window,mode=relative'},
                        template_path:{type:'path',label:'模板图片路径(.png/.jpg)',default:'',browseType:'template',varRef:true},
                        threshold:{type:'number',label:'匹配阈值(0.5~1.0)',default:0.8,varRef:true},
                        method:{type:'enum',label:'匹配算法',default:'tm_ccoeff_normed',options:['tm_ccoeff_normed','tm_ccorr_normed','tm_sqdiff_normed'],display_names:{'tm_ccoeff_normed':'相关系数(推荐)','tm_ccorr_normed':'相关系数(无归一化)','tm_sqdiff_normed':'平方差'}},
                        multi_match:{type:'bool',label:'多目标匹配',default:false},
                        pyramid_levels:{type:'number',label:'金字塔层数',default:2,varRef:true},
                        store_var:{type:'string',label:'存储坐标到变量 (可选)',default:'',varRef:true,placeholder:'留空则不存储，格式: {x, y, confidence}'},
                        cache_strategy:{type:'enum',label:'缓存策略',default:'time_interval',options:['frame_diff','time_interval','disabled'],display_names:{'frame_diff':'帧差分(高灵敏度)','time_interval':'时间间隔(低占用)','disabled':'不缓存(实时)'}},
                        cache_interval_ms:{type:'number',label:'缓存间隔(ms)',default:100,showWhen:'cache_strategy=time_interval',varRef:true},
                        wait:{type:'bool',label:'持续等待',default:false},
                        wait_interval_ms:{type:'number',label:'轮询间隔(ms)',default:16,showWhen:'wait=true',varRef:true},
                        wait_timeout_ms:{type:'number',label:'等待超时(ms)',default:5000,showWhen:'wait=true',varRef:true} }},
                'detection/check_screen': { display_name: '屏幕状态', color: '#eab308', category: 'detection', icon: 'fa-solid fa-display',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'match',type:'flow'},{name:'no',type:'flow'},{name:'result',type:'boolean'}],
                    params_schema: { mode:{type:'enum',label:'坐标模式',default:'screen',options:['screen','window','relative'],coordMode:true,display_names:{'screen':'屏幕坐标','window':'窗口坐标','relative':'相对坐标(0~1)'}},
                        hwnd_var:{type:'string',label:'窗口句柄变量名',default:'',varRef:true,showWhen:'mode=window,mode=relative'},
                        state:{type:'enum',label:'检测状态',default:'black',options:['black','bright','frozen'],display_names:{'black':'黑屏检测','bright':'白屏检测','frozen':'画面冻结检测'}},
                        threshold:{type:'number',label:'阈值',default:30,varRef:true,descMap:{black:'亮度阈值(低于此值判定为黑屏)',bright:'亮度阈值(高于255-此值判定为白屏)',frozen:'差异阈值(低于此值判定为画面冻结)'},descMapCond:'state'},
                        frozen_duration_ms:{type:'number',label:'冻结判定间隔(ms)',default:200,showWhen:'state=frozen',varRef:true},
                        region:{type:'region',label:'检测区域',default:[0,0,0,0],varRef:true},
                        wait:{type:'bool',label:'持续等待',default:false},
                        wait_interval_ms:{type:'number',label:'轮询间隔(ms)',default:16,showWhen:'wait=true',varRef:true},
                        wait_timeout_ms:{type:'number',label:'等待超时(ms)',default:5000,showWhen:'wait=true',varRef:true} }},
                'control/wait_cond': { display_name: '等待条件', color: '#a855f7', category: 'control', icon: 'fa-solid fa-clock',
                    inputs: [{name:'in',type:'flow'},{name:'cond',type:'boolean'}],
                    outputs: [{name:'met',type:'flow'},{name:'timeout',type:'flow'}],
                    params_schema: { timeout:{type:'number',label:'超时(ms)',default:10000,varRef:true},
                        interval:{type:'number',label:'检查间隔(ms)',default:100,varRef:true} }},
                'control/goto': { display_name: '跳转', color: '#a855f7', category: 'control', icon: 'fa-solid fa-forward-fast',
                    inputs: [{name:'in',type:'flow'}], outputs: [],
                    params_schema: { target_node_id:{type:'string',label:'目标节点ID',default:'',varRef:true} }},
                'control/seq_check': { display_name: '序列检测', color: '#a855f7', category: 'control', icon: 'fa-solid fa-list-check',
                    inputs: [{name:'in',type:'flow'},{name:'cond',type:'data_bool'}], outputs: [{name:'pass',type:'flow'},{name:'fail',type:'flow'}],
                    params_schema: {
                        retry:{type:'bool',label:'失败重试',default:true,description:'关闭则只检测一次，失败直接走fail分支'},
                        max_retries:{type:'number',label:'最大重试次数',default:100,varRef:true,placeholder:'例: 100=最多等10秒'},
                        poll_interval_ms:{type:'number',label:'轮询间隔(ms)',default:100,varRef:true} }},
                'control/state_machine': { display_name: '状态机', color: '#a855f7', category: 'control', icon: 'fa-solid fa-circle-nodes',
                    inputs: [{name:'in',type:'flow'},{name:'cond',type:'data_bool'}], outputs: [{name:'done',type:'flow'}],
                    params_schema: {
                        states:{type:'string',label:'状态列表',default:'',varRef:true,placeholder:'待机→攻击→冷却→待机'},
                        fail_state:{type:'string',label:'失败回退',default:'',varRef:true,placeholder:'待机（留空=失败也前进）'},
                        poll_interval_ms:{type:'number',label:'轮询间隔(ms)',default:100,varRef:true} }},
                'control/fork': { display_name: '并发执行', color: '#a855f7', category: 'control', icon: 'fa-solid fa-code-fork',
                    inputs: [{name:'in',type:'flow'}],
                    outputs: [{name:'next',type:'flow',display_name:'立即'},{name:'done',type:'flow',display_name:'完成'},{name:'branch1',type:'flow'},{name:'branch2',type:'flow'}],
                    dynamic_branches: true,
                    params_schema: {
                        branch_count:{type:'number',label:'分支数量',default:2,min:2,max:8},
                        branch_name_1:{type:'string',label:'分支1名称',default:''},
                        branch_name_2:{type:'string',label:'分支2名称',default:''},
                        branch_name_3:{type:'string',label:'分支3名称',default:'',showWhen:'branch_count>=3'},
                        branch_name_4:{type:'string',label:'分支4名称',default:'',showWhen:'branch_count>=4'},
                        branch_name_5:{type:'string',label:'分支5名称',default:'',showWhen:'branch_count>=5'},
                        branch_name_6:{type:'string',label:'分支6名称',default:'',showWhen:'branch_count>=6'},
                        branch_name_7:{type:'string',label:'分支7名称',default:'',showWhen:'branch_count>=7'},
                        branch_name_8:{type:'string',label:'分支8名称',default:'',showWhen:'branch_count>=8'},
                        branch_affinity_1:{type:'affinity',label:'分支1绑核',default:{enabled:false,core:-1}},
                        branch_affinity_2:{type:'affinity',label:'分支2绑核',default:{enabled:false,core:-1}},
                        branch_affinity_3:{type:'affinity',label:'分支3绑核',default:{enabled:false,core:-1},showWhen:'branch_count>=3'},
                        branch_affinity_4:{type:'affinity',label:'分支4绑核',default:{enabled:false,core:-1},showWhen:'branch_count>=4'},
                        branch_affinity_5:{type:'affinity',label:'分支5绑核',default:{enabled:false,core:-1},showWhen:'branch_count>=5'},
                        branch_affinity_6:{type:'affinity',label:'分支6绑核',default:{enabled:false,core:-1},showWhen:'branch_count>=6'},
                        branch_affinity_7:{type:'affinity',label:'分支7绑核',default:{enabled:false,core:-1},showWhen:'branch_count>=7'},
                        branch_affinity_8:{type:'affinity',label:'分支8绑核',default:{enabled:false,core:-1},showWhen:'branch_count>=8'} }},
                'control/join': { display_name: '等待汇合', color: '#a855f7', category: 'control', icon: 'fa-solid fa-object-ungroup',
                    inputs: [{name:'branch1',type:'flow'},{name:'branch2',type:'flow'}],
                    outputs: [{name:'done',type:'flow'}],
                    dynamic_branches: true,
                    params_schema: {
                        branch_count:{type:'number',label:'分支数量',default:2,min:2,max:8},
                        wait_mode:{type:'enum',label:'等待模式',default:'all',options:['all','any','custom'],display_names:{'all':'全部到达(等所有分支)','any':'任一到达(任一即继续)','custom':'自定义(手动勾选)'}},
                        branch_required_1:{type:'bool',label:'分支1必须到达',default:true,showWhen:'wait_mode=custom'},
                        branch_required_2:{type:'bool',label:'分支2必须到达',default:true,showWhen:'wait_mode=custom'},
                        branch_required_3:{type:'bool',label:'分支3必须到达',default:true,showWhen:'wait_mode=custom,branch_count>=3'},
                        branch_required_4:{type:'bool',label:'分支4必须到达',default:true,showWhen:'wait_mode=custom,branch_count>=4'},
                        branch_required_5:{type:'bool',label:'分支5必须到达',default:true,showWhen:'wait_mode=custom,branch_count>=5'},
                        branch_required_6:{type:'bool',label:'分支6必须到达',default:true,showWhen:'wait_mode=custom,branch_count>=6'},
                        branch_required_7:{type:'bool',label:'分支7必须到达',default:true,showWhen:'wait_mode=custom,branch_count>=7'},
                        branch_required_8:{type:'bool',label:'分支8必须到达',default:true,showWhen:'wait_mode=custom,branch_count>=8'},
                        timeout_ms:{type:'number',label:'超时(ms)',default:30000,varRef:true},
                        cancel_others:{type:'bool',label:'触发后取消未到达分支',default:false},
                        target_fork_node_id:{type:'string',label:'目标Fork/Race节点ID',default:'',nodeRef:'fork_race'} }},
                'control/race': { display_name: '竞争执行', color: '#a855f7', category: 'control', icon: 'fa-solid fa-bolt',
                    inputs: [{name:'in',type:'flow'}],
                    outputs: [{name:'branch1',type:'flow'},{name:'branch2',type:'flow'}],
                    dynamic_branches: true,
                    params_schema: {
                        branch_count:{type:'number',label:'分支数量',default:2,min:2,max:8},
                        branch_name_1:{type:'string',label:'分支1名称',default:''},
                        branch_name_2:{type:'string',label:'分支2名称',default:''},
                        branch_name_3:{type:'string',label:'分支3名称',default:'',showWhen:'branch_count>=3'},
                        branch_name_4:{type:'string',label:'分支4名称',default:'',showWhen:'branch_count>=4'},
                        branch_name_5:{type:'string',label:'分支5名称',default:'',showWhen:'branch_count>=5'},
                        branch_name_6:{type:'string',label:'分支6名称',default:'',showWhen:'branch_count>=6'},
                        branch_name_7:{type:'string',label:'分支7名称',default:'',showWhen:'branch_count>=7'},
                        branch_name_8:{type:'string',label:'分支8名称',default:'',showWhen:'branch_count>=8'},
                        branch_affinity_1:{type:'affinity',label:'分支1绑核',default:{enabled:false,core:-1}},
                        branch_affinity_2:{type:'affinity',label:'分支2绑核',default:{enabled:false,core:-1}},
                        branch_affinity_3:{type:'affinity',label:'分支3绑核',default:{enabled:false,core:-1},showWhen:'branch_count>=3'},
                        branch_affinity_4:{type:'affinity',label:'分支4绑核',default:{enabled:false,core:-1},showWhen:'branch_count>=4'},
                        branch_affinity_5:{type:'affinity',label:'分支5绑核',default:{enabled:false,core:-1},showWhen:'branch_count>=5'},
                        branch_affinity_6:{type:'affinity',label:'分支6绑核',default:{enabled:false,core:-1},showWhen:'branch_count>=6'},
                        branch_affinity_7:{type:'affinity',label:'分支7绑核',default:{enabled:false,core:-1},showWhen:'branch_count>=7'},
                        branch_affinity_8:{type:'affinity',label:'分支8绑核',default:{enabled:false,core:-1},showWhen:'branch_count>=8'},
                        cancel_on_first:{type:'bool',label:'首个到达后取消其他',default:true},
                        timeout_ms:{type:'number',label:'超时(ms)',default:0,varRef:true} }},
                'control/race_win': { display_name: '竞争胜出', color: '#f59e0b', category: 'control', icon: 'fa-solid fa-trophy',
                    inputs: [{name:'in',type:'flow'}],
                    outputs: [{name:'next',type:'flow'},{name:'winner_branch',type:'data_string'}],
                    params_schema: {} },
                'control/stop_branch': { display_name: '停止分支', color: '#a855f7', category: 'control', icon: 'fa-solid fa-ban',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { target_branch:{type:'string',label:'目标分支ID',default:'all_others',varRef:true,branchRef:true} }},
                'control/pause_branch': { display_name: '暂停分支', color: '#a855f7', category: 'control', icon: 'fa-solid fa-pause',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { target_branch:{type:'string',label:'目标分支ID',default:'all_others',varRef:true,branchRef:true} }},
                'control/resume_branch': { display_name: '恢复分支', color: '#a855f7', category: 'control', icon: 'fa-solid fa-play',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { target_branch:{type:'string',label:'目标分支ID',default:'all_others',varRef:true,branchRef:true} }},
                'preset/preset_click': { display_name: '点击坐标', color: '#f472b6', category: 'preset', icon: 'fa-solid fa-bullseye',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { mode:{type:'enum',label:'坐标模式',default:'screen',options:['screen','window','relative'],display_names:{'screen':'屏幕坐标','window':'窗口坐标','relative':'相对坐标(0~1)'}},
                        x:{type:'number',label:'X坐标(像素)',default:960,coordRef:true,varRef:true}, y:{type:'number',label:'Y坐标(像素)',default:540,coordRef:true,varRef:true},
                        hwnd_var:{type:'string',label:'窗口句柄变量名',default:'',varRef:true,showWhen:'mode=window,mode=relative'},
                        button:{type:'enum',label:'鼠标按键',default:'left',options:['left','right','middle'],display_names:{'left':'左键','right':'右键','middle':'中键'}},
                        move_duration:{type:'number',label:'移动耗时',default:150,varRef:true} }},
                'preset/preset_find_click': { display_name: '找图点击', color: '#f472b6', category: 'preset', icon: 'fa-solid fa-crosshairs',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'found',type:'flow'},{name:'not_found',type:'flow'}],
                    params_schema: { mode:{type:'enum',label:'坐标模式',default:'screen',options:['screen','window','relative'],coordMode:true,display_names:{'screen':'屏幕坐标','window':'窗口坐标','relative':'相对坐标(0~1)'}},
                        rect:{type:'region',label:'搜索区域(全零=全屏)',default:[0,0,0,0],coordMode:true,varRef:true}, hwnd_var:{type:'string',label:'窗口句柄变量名',default:'',varRef:true,showWhen:'mode=window,mode=relative'},
                        template_path:{type:'path',label:'模板图片路径(.png/.jpg)',default:'',browseType:'template',varRef:true},
                        threshold:{type:'number',label:'匹配阈值(0.5~1.0)',default:0.8,varRef:true},
                        button:{type:'enum',label:'鼠标按键',default:'left',options:['left','right','middle'],display_names:{'left':'左键','right':'右键','middle':'中键'}},
                        store_var:{type:'string',label:'存入变量(是否找到)',default:'',varRef:true} }},
                'preset/preset_read_text': { display_name: '读取数字文本', color: '#f472b6', category: 'preset', icon: 'fa-solid fa-hashtag',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'},{name:'text',type:'data_string'}],
                    params_schema: { mode:{type:'enum',label:'坐标模式',default:'screen',options:['screen','window','relative'],coordMode:true,display_names:{'screen':'屏幕坐标','window':'窗口坐标','relative':'相对坐标(0~1)'}},
                        rect:{type:'region',label:'检测区域[x,y,w,h]',default:[0,0,100,30],coordMode:true,varRef:true}, hwnd_var:{type:'string',label:'窗口句柄变量名',default:'',varRef:true,showWhen:'mode=window,mode=relative'},
                        read_mode:{type:'enum',label:'读取模式',default:'all',options:['all','number','text'],display_names:{'all':'全部识别','number':'仅提取数字','text':'仅提取文本'}},
                        store_var:{type:'string',label:'存入变量',default:'',varRef:true},
                        store_number:{type:'string',label:'数值存入变量',default:'',varRef:true,showWhen:'read_mode=number'} }},
                'script_block/flow_control': { display_name: '动作控制', color: '#3b82f6', category: 'script_block', icon: 'fa-solid fa-sliders',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: {
                        action:{type:'enum',label:'控制动作',default:'stop_all',options:['stop_all','stop_task','pause_task','resume_task','stop_self','nothing'],display_names:{'stop_all':'停止所有任务','stop_task':'停止指定任务','pause_task':'暂停指定任务','resume_task':'恢复指定任务','stop_self':'停止自身(当前脚本)','nothing':'无操作(占位)'}},
                        target_task:{type:'string',label:'目标任务ID',default:'',showWhen:'action=stop_task,action=pause_task,action=resume_task',nodeRef:'script_block/call_script_async,script_block/exec_sub_script',varRef:true}
                    }},
                'script_block/exec_sub_script': { display_name: '执行子脚本', color: '#3b82f6', category: 'script_block', icon: 'fa-solid fa-file-code',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'},{name:'fail',type:'flow'}],
                    params_schema: { script_path:{type:'path',label:'子脚本文件',default:'',browseType:'script',varRef:true} }},
                'utility/const_number': { display_name: '数字常量', color: '#d8d8d8ff', category: 'utility', icon: 'fa-solid fa-hashtag',
                    inputs: [], outputs: [{name:'value',type:'number'}],
                    params_schema: { value:{type:'number',label:'值',default:0,varRef:true} }},
                'utility/const_string': { display_name: '字符串常量', color: '#d8d8d8ff', category: 'utility', icon: 'fa-solid fa-quote-right',
                    inputs: [], outputs: [{name:'value',type:'string'}],
                    params_schema: { value:{type:'string',label:'值',default:'',varRef:true} }},
                'utility/const_bool': { display_name: '布尔常量', color: '#d8d8d8ff', category: 'utility', icon: 'fa-solid fa-toggle-on',
                    inputs: [], outputs: [{name:'value',type:'boolean'}],
                    params_schema: { value:{type:'bool',label:'布尔值',default:true,display_names:{true:'真',false:'假'}} }},
                'utility/math_op': { display_name: '数学运算', color: '#d8d8d8ff', category: 'utility', icon: 'fa-solid fa-calculator',
                    inputs: [{name:'A',type:'number'},{name:'B',type:'number'}], outputs: [{name:'result',type:'number'}],
                    params_schema: { op:{type:'enum',label:'运算符',default:'+',options:['+','-','*','/','%','^','min','max'],display_names:{'+':'加法(+)','-':'减法(-)','*':'乘法(×)','/':'除法(÷)','%':'取余(模)','^':'乘方(幂)','min':'取最小值','max':'取最大值'}},
                        a:{type:'number',label:'A',default:0,varRef:true}, b:{type:'number',label:'B',default:0,varRef:true} }},
                'utility/math_func': { display_name: '数学函数', color: '#d8d8d8ff', category: 'utility', icon: 'fa-solid fa-square-root-variable',
                    inputs: [{name:'x',type:'number'}], outputs: [{name:'result',type:'number'}],
                    params_schema: { func:{type:'enum',label:'数学函数',default:'abs',options:['abs','round','floor','ceil','sqrt','sin','cos','log','negate'],display_names:{'abs':'绝对值(|x|)','round':'四舍五入','floor':'向下取整(⌊x⌋)','ceil':'向上取整(⌈x⌉)','sqrt':'平方根(√)','sin':'正弦(sin)','cos':'余弦(cos)','log':'自然对数(ln)','negate':'取负(-x)'}},
                        x:{type:'number',label:'x',default:0,varRef:true},
                        digits:{type:'number',label:'小数位数',default:0,varRef:true,showWhen:'func=round'} }},
                'utility/logic_op': { display_name: '逻辑运算', color: '#d8d8d8ff', category: 'utility', icon: 'fa-solid fa-code-merge',
                    inputs: [{name:'A',type:'boolean'},{name:'B',type:'boolean'}], outputs: [{name:'result',type:'boolean'}],
                    params_schema: { op:{type:'enum',label:'逻辑运算',default:'and',options:['and','or','xor','not','nand','nor'],display_names:{'and':'与(AND, 全真则真)','or':'或(OR, 有真则真)','xor':'异或(XOR, 不同为真)','not':'非(NOT, 取反)','nand':'与非(NAND)','nor':'或非(NOR)'}},
                        a:{type:'bool',label:'A',default:true,varRef:true}, b:{type:'bool',label:'B',default:true,varRef:true,showWhen:'op=and,op=or,op=xor,op=nand,op=nor'} }},
                'utility/compare': { display_name: '数值比较', color: '#d8d8d8ff', category: 'utility', icon: 'fa-solid fa-not-equal',
                    inputs: [{name:'A',type:'number'},{name:'B',type:'number'}], outputs: [{name:'result',type:'boolean'}],
                    params_schema: { op:{type:'enum',label:'比较运算符',default:'gt',options:['eq','ne','gt','lt','ge','le'],display_names:{'eq':'等于(==)','ne':'不等于(!=)','gt':'大于(>)','lt':'小于(<)','ge':'大于等于(≥)','le':'小于等于(≤)'}},
                        a:{type:'number',label:'A',default:0,varRef:true}, b:{type:'number',label:'B',default:0,varRef:true} }},
                'utility/string_op': { display_name: '字符串操作', color: '#d8d8d8ff', category: 'utility', icon: 'fa-solid fa-font',
                    inputs: [{name:'str',type:'string'}], outputs: [{name:'result',type:'string'}],
                    params_schema: { op:{type:'enum',label:'操作类型',default:'concat',options:['concat','replace','upper','lower','trim','substring','split_index','regex_extract'],display_names:{'concat':'拼接(合并)','replace':'替换(查找替换)','upper':'转大写','lower':'转小写','trim':'去首尾空格','substring':'截取子串','split_index':'分割取段','regex_extract':'正则提取'}},
                        input_str:{type:'string',label:'输入',default:'',varRef:true},
                        concat_str:{type:'string',label:'拼接字符串',default:'',varRef:true,showWhen:'op=concat'},
                        search_str:{type:'string',label:'查找文本',default:'',varRef:true,showWhen:'op=replace'},
                        replace_str:{type:'string',label:'替换为',default:'',varRef:true,showWhen:'op=replace'},
                        start_pos:{type:'number',label:'起始位置',default:0,showWhen:'op=substring',varRef:true},
                        length:{type:'number',label:'截取长度',default:0,showWhen:'op=substring',varRef:true},
                        delimiter:{type:'string',label:'分隔符(如逗号、竖线)',default:',',varRef:true,showWhen:'op=split_index'},
                        index:{type:'number',label:'取第几段(从0开始)',default:0,showWhen:'op=split_index',varRef:true},
                        pattern:{type:'string',label:'正则表达式(如\\d+匹配数字)',default:'',varRef:true,showWhen:'op=regex_extract'},
                        group:{type:'number',label:'捕获组编号',default:0,showWhen:'op=regex_extract',varRef:true} }},
                'utility/condition': { display_name: '条件选择', color: '#d8d8d8ff', category: 'utility', icon: 'fa-solid fa-code-branch',
                    inputs: [{name:'cond',type:'boolean'},{name:'if_true',type:'any'},{name:'if_false',type:'any'}], outputs: [{name:'result',type:'any'}],
                    params_schema: { cond_var:{type:'string',label:'条件变量',default:'',varRef:true},
                        true_val:{type:'string',label:'真值',default:'',varRef:true}, false_val:{type:'string',label:'假值',default:'',varRef:true} }},
                'utility/delay': { display_name: '延迟', color: '#d8d8d8ff', category: 'utility', icon: 'fa-solid fa-hourglass-half',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { ms:{type:'number',label:'延迟(ms)',default:1000,varRef:true} }},
                'utility/bookmark': { display_name: '坐标书签', color: '#d8d8d8ff', category: 'utility', icon: 'fa-solid fa-bookmark',
                    inputs: [], outputs: [{name:'x',type:'number'},{name:'y',type:'number'},{name:'w',type:'number'},{name:'h',type:'number'}],
                    params_schema: { name:{type:'string',label:'书签名称',default:''}, mode:{type:'enum',label:'坐标模式',default:'screen',options:['screen','window','relative'],display_names:{'screen':'屏幕坐标','window':'窗口坐标','relative':'相对坐标(0~1)'}},
                        x:{type:'number',label:'X坐标(像素)',default:0,pickable:true,varRef:true}, y:{type:'number',label:'Y坐标(像素)',default:0,pickable:true,varRef:true},
                        w:{type:'number',label:'宽度(像素)',default:0,pickable:true,varRef:true}, h:{type:'number',label:'高度(像素)',default:0,pickable:true,varRef:true},
                        hwnd_var:{type:'string',label:'窗口句柄变量名',default:'',varRef:true,showWhen:'mode=window,mode=relative'}, remark:{type:'string',label:'备注',default:''} }},
                'flow/start': { display_name: '开始', color: '#99ff00ff', category: 'flow', icon: 'fa-solid fa-play',
                    inputs: [], outputs: [{name:'next',type:'flow'}],
                    params_schema: {
                        boost_priority:{type:'bool',label:'提升进程优先级',default:true,display_names:{true:'是(推荐)',false:'否'}},
                        affinity_enabled:{type:'bool',label:'CPU绑核',default:false,display_names:{true:'启用绑核',false:'不绑核'}},
                        affinity_core:{type:'number',label:'核心号(-1自动)',default:-1,showWhen:'affinity_enabled=true'}
                    } },
                'flow/end': { display_name: '结束', color: '#ef4444', category: 'flow', icon: 'fa-solid fa-stop',
                    inputs: [{name:'in',type:'flow'}], outputs: [],
                    params_schema: {} },
            };

            for (var type in fallbackDefs) {
                if (!fallbackDefs.hasOwnProperty(type)) continue;
                this._processAndRegisterNodeDef(type, fallbackDefs[type]);
            }
        },

        getNodeDef: function(type) {
            return this._nodeDefs[type] || null;
        },

        getCategories: function() {
            return this._categories;
        },

        toZhPortName: _toZh,

        generateDefaults: function(schema) {
            var props = {};
            if (!schema) return props;
            for (var key in schema) {
                if (!schema.hasOwnProperty(key)) continue;
                var s = schema[key];
                if (s.type === 'region') {
                    props[key] = s.default ? s.default.slice() : [0, 0, 10, 10];
                } else if (s.type === 'var_list') {
                    props[key] = s.default || '[]';
                } else if (s.type === 'bool' || s.type === 'boolean') {
                    props[key] = !!s.default;
                } else {
                    props[key] = s.default !== undefined ? s.default : (s.type === 'number' ? 0 : '');
                }
            }
            return props;
        },

        registerPluginNodes: function(nodes) {
            if (!nodes || typeof nodes !== 'object') return;
            for (var typeKey in nodes) {
                if (!nodes.hasOwnProperty(typeKey)) continue;
                var def = nodes[typeKey];
                this._normalizeSchema(def);
                if (def.dynamic_branches) {
                    this._expandDynamicBranches(def);
                    this._normalizeSchema(def);
                }
                var existing = this._nodeDefs[typeKey];
                if (existing) {
                    var existingParams = existing.params_schema || {};
                    var newParams = def.params_schema || {};
                    var hasPlaceholder = newParams.__placeholder;
                    var existingIsRicher = Object.keys(existingParams).length > Object.keys(newParams).length;
                    if (hasPlaceholder || existingIsRicher) continue;
                }
                this._nodeDefs[typeKey] = def;
                var cat = def.category || 'plugin';
                if (!this._categories[cat]) {
                    this._categories[cat] = { name: '插件', color: def.color || '#a855f7', nodes: [] };
                }
                var exists = false;
                for (var i = 0; i < this._categories[cat].nodes.length; i++) {
                    if (this._categories[cat].nodes[i].type === typeKey) { exists = true; break; }
                }
                if (!exists) {
                    this._categories[cat].nodes.push({ type: typeKey, name: def.display_name, icon: def.icon || '' });
                }
            }
        }
    };

export const AutomationNodes = window.AutomationNodes;
