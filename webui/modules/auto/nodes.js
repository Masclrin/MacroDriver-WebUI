'use strict';

var _portNameMap = {
        in: '执行', out: '输出', next: '下一步', body: '循环体',
        done: '完成', true: '是', false: '否', cond: '条件',
        trigger: '触发', timeout: '超时', completed: '完成',
        interrupted: '中断', match: '匹配', no: '不匹配',
        result: '结果', val: '值',
        x: 'X', y: 'Y', w: '宽', h: '高',
        A: 'A', B: 'B', str: '字符串',
        text: '文本', number: '数值', color: '颜色',
        match_x: '匹配X', match_y: '匹配Y',
        if_true: '真值', if_false: '假值',
    };

    function _toZh(name) {
        return _portNameMap[name] || name;
    }

    window.AutomationNodes = {
        _nodeDefs: {},
        _categories: {},

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
            var catNames = { action:'动作节点', detection:'检测节点', control:'控制节点', script_block:'动作块', monitor:'监视器', variable:'变量', preset:'预设', utility:'工具', flow:'流程', plugin:'插件' };
            var catColors = { action:'#22c55e', detection:'#eab308', control:'#a855f7', script_block:'#3b82f6', monitor:'#06b6d4', variable:'#f97316', preset:'#f472b6', utility:'#adadadff', flow:'#ff0000ff', plugin:'#a855f7' };
            for (var type in nodes) {
                if (!nodes.hasOwnProperty(type)) continue;
                var def = nodes[type];
                this._nodeDefs[type] = def;
                var cat = def.category || 'other';
                if (!this._categories[cat]) {
                    this._categories[cat] = { name: catNames[cat] || cat, color: catColors[cat] || def.color || '#888', nodes: [] };
                }
                this._categories[cat].nodes.push({ type: type, name: def.display_name, icon: def.icon || '' });
            }
        },

        _registerFallback: function() {
            var fallbackDefs = {
                'action/mouse_click': { display_name: '鼠标点击', color: '#22c55e', category: 'action', icon: 'fa-solid fa-arrow-pointer',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { mode:{type:'enum',label:'坐标模式',default:'screen',options:['screen','window','relative']},
                        x:{type:'number',label:'X',default:0,coordRef:true,varRef:true}, y:{type:'number',label:'Y',default:0,coordRef:true,varRef:true},
                        hwnd_var:{type:'string',label:'窗口变量',default:'',varRef:true},
                        button:{type:'enum',label:'按钮',default:'left',options:['left','right','middle']},
                        click_type:{type:'enum',label:'点击方式',default:'click',options:['click','dblclick','press','release','long_press']},
                        hold_time:{type:'number',label:'长按时长',default:0,varRef:true}, move_duration:{type:'number',label:'移动耗时',default:0,varRef:true},
                        before_delay:{type:'number',label:'前延迟',default:0,varRef:true}, after_delay:{type:'number',label:'后延迟',default:0,varRef:true} }},
                'action/key_action': { display_name: '按键动作', color: '#22c55e', category: 'action', icon: 'fa-solid fa-keyboard',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { action:{type:'enum',label:'动作',default:'press',options:['press','release','type']},
                        key:{type:'string',label:'按键',default:'a',varRef:true}, delay:{type:'number',label:'后延迟',default:0,varRef:true} }},
                'action/mouse_scroll': { display_name: '鼠标滚轮', color: '#22c55e', category: 'action', icon: 'fa-solid fa-arrows-up-down',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { delta:{type:'number',label:'滚动量',default:120,varRef:true}, delay:{type:'number',label:'后延迟',default:0,varRef:true} }},
                'action/text_input': { display_name: '文本输入', color: '#22c55e', category: 'action', icon: 'fa-solid fa-font',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { text:{type:'string',label:'文本内容',default:'',varRef:true}, interval:{type:'number',label:'字符间隔',default:50,varRef:true},
                        before_delay:{type:'number',label:'前延迟',default:0,varRef:true} }},
                'action/wait': { display_name: '等待', color: '#22c55e', category: 'action', icon: 'fa-solid fa-clock',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { duration:{type:'number',label:'时长',default:1000,varRef:true} }},
                'detection/check_color': { display_name: '颜色检测', color: '#eab308', category: 'detection', icon: 'fa-solid fa-palette',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'match',type:'flow'},{name:'no',type:'flow'},{name:'result',type:'boolean'},{name:'color',type:'string'}],
                    params_schema: { mode:{type:'enum',label:'坐标模式',default:'screen',options:['screen','window','relative'],coordMode:true},
                        rect:{type:'region',label:'检测区域',default:[0,0,10,10],coordMode:true}, hwnd_var:{type:'string',label:'窗口变量',default:'',varRef:true},
                        target_color:{type:'color',label:'目标颜色',default:'#FF0000'}, tolerance:{type:'number',label:'容差',default:10,varRef:true},
                        check_mode:{type:'enum',label:'检测方式',default:'contain',options:['exact','contain','change']},
                        change_threshold:{type:'number',label:'变化阈值',default:10,showWhen:'check_mode=change',varRef:true},
                        sample_mode:{type:'enum',label:'采样方式',default:'center',options:['center','mean','max_diff']},
                        store_var:{type:'string',label:'存入变量',default:''} }},
                'detection/check_ocr': { display_name: 'OCR识别', color: '#eab308', category: 'detection', icon: 'fa-solid fa-language',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'match',type:'flow'},{name:'no',type:'flow'},{name:'result',type:'boolean'},{name:'text',type:'string'},{name:'number',type:'number'}],
                    params_schema: { mode:{type:'enum',label:'坐标模式',default:'screen',options:['screen','window','relative'],coordMode:true},
                        rect:{type:'region',label:'检测区域',default:[0,0,100,30],coordMode:true}, hwnd_var:{type:'string',label:'窗口变量',default:''},
                        match_text:{type:'string',label:'匹配文本',default:''},
                        match_mode:{type:'enum',label:'匹配方式',default:'contain',options:['contain','exact','regex','number_gt','number_lt','number_eq']},
                        match_number:{type:'number',label:'比较数值',default:0,showWhen:'match_mode=number_gt,number_lt,number_eq'},
                        engine:{type:'enum',label:'OCR引擎',default:'rapidocr',options:['rapidocr']},
                        store_var:{type:'string',label:'存入变量',default:''},
                        store_number:{type:'string',label:'存入变量',default:'',showWhen:'match_mode=number_gt,number_lt,number_eq'},
                        cache_strategy:{type:'enum',label:'缓存策略',default:'time_interval',options:['frame_diff','time_interval','disabled']},
                        cache_interval_ms:{type:'number',label:'缓存间隔',default:100,showWhen:'cache_strategy=time_interval'} }},
                'control/if_else': { display_name: '条件分支', color: '#a855f7', category: 'control', icon: 'fa-solid fa-code-branch',
                    inputs: [{name:'in',type:'flow'},{name:'cond',type:'boolean'}],
                    outputs: [{name:'true',type:'flow'},{name:'false',type:'flow'}],
                    params_schema: { logic:{type:'enum',label:'逻辑组合',default:'AND',options:['AND','OR','NOT']},
                        fallback:{type:'enum',label:'无输入时',default:'false',options:['true','false']} }},
                'control/loop_count': { display_name: '计数循环', color: '#a855f7', category: 'control', icon: 'fa-solid fa-repeat',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'body',type:'flow'},{name:'next',type:'flow'}],
                    params_schema: { count:{type:'number',label:'循环次数',default:5,varRef:true}, counter_var:{type:'string',label:'计数器变量',default:''} }},
                'control/loop_while': { display_name: '条件循环', color: '#a855f7', category: 'control', icon: 'fa-solid fa-rotate',
                    inputs: [{name:'in',type:'flow'},{name:'cond',type:'boolean'}],
                    outputs: [{name:'body',type:'flow'},{name:'next',type:'flow'}],
                    params_schema: { max_iterations:{type:'number',label:'最大迭代',default:10000,varRef:true},
                        check_at:{type:'enum',label:'检查时机',default:'start',options:['start','end']} }},
                'script_block/call_script_sync': { display_name: '调用宏(同步)', color: '#3b82f6', category: 'script_block', icon: 'fa-solid fa-play',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { path:{type:'path',label:'宏文件路径',default:''}, speed_factor:{type:'number',label:'倍速',default:1.0},
                        timeline_mode:{type:'enum',label:'时间线',default:'absolute',options:['absolute','relative_compensated']},
                        random_delay:{type:'bool',label:'随机延迟修正',default:false} }},
                'script_block/call_script_async': { display_name: '调用宏(异步)', color: '#3b82f6', category: 'script_block', icon: 'fa-solid fa-forward',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'},{name:'completed',type:'flow'},{name:'interrupted',type:'flow'}],
                    params_schema: { path:{type:'path',label:'宏文件路径',default:''}, speed_factor:{type:'number',label:'倍速',default:1.0},
                        timeline_mode:{type:'enum',label:'时间线',default:'absolute',options:['absolute','relative_compensated']},
                        random_delay:{type:'bool',label:'随机延迟修正',default:false} }},
                'monitor/monitor_color': { display_name: '颜色监视', color: '#06b6d4', category: 'monitor', icon: 'fa-solid fa-eye',
                    inputs: [], outputs: [{name:'trigger',type:'flow'},{name:'timeout',type:'flow'}],
                    params_schema: { mode:{type:'enum',label:'坐标模式',default:'screen',options:['screen','window','relative'],coordMode:true},
                        rect:{type:'region',label:'检测区域',default:[0,0,10,10],coordMode:true,varRef:true}, hwnd_var:{type:'string',label:'窗口变量',default:'',varRef:true},
                        target_color:{type:'color',label:'目标颜色',default:'#FF0000'}, tolerance:{type:'number',label:'容差',default:10,varRef:true},
                        interval:{type:'number',label:'检测间隔',default:100,varRef:true}, timeout:{type:'number',label:'超时',default:0,varRef:true},
                        trigger_mode:{type:'enum',label:'触发模式',default:'appear',options:['appear','disappear','change']},
                        on_trigger:{type:'enum',label:'触发行为',default:'branch',options:['branch','stop_all','stop_task','pause_task']},
                        auto_stop:{type:'bool',label:'触发后自动停止',default:true} }},
                'monitor/monitor_ocr': { display_name: 'OCR监视', color: '#06b6d4', category: 'monitor', icon: 'fa-solid fa-eye',
                    inputs: [], outputs: [{name:'trigger',type:'flow'},{name:'timeout',type:'flow'}],
                    params_schema: { mode:{type:'enum',label:'坐标模式',default:'screen',options:['screen','window','relative'],coordMode:true},
                        rect:{type:'region',label:'检测区域',default:[0,0,100,30],coordMode:true,varRef:true}, hwnd_var:{type:'string',label:'窗口变量',default:'',varRef:true},
                        match_text:{type:'string',label:'匹配文本',default:'',varRef:true},
                        match_mode:{type:'enum',label:'匹配方式',default:'contain',options:['contain','exact','regex','number_gt','number_lt','number_eq']},
                        match_number:{type:'number',label:'比较数值',default:0,varRef:true,showWhen:'match_mode=number_gt,number_lt,number_eq'},
                        engine:{type:'enum',label:'OCR引擎',default:'rapidocr',options:['rapidocr']},
                        interval:{type:'number',label:'检测间隔',default:200,varRef:true}, timeout:{type:'number',label:'超时',default:0,varRef:true},
                        on_trigger:{type:'enum',label:'触发行为',default:'branch',options:['branch','stop_all','stop_task','pause_task']},
                        store_var:{type:'string',label:'存入变量',default:'',varRef:true},
                        store_number:{type:'string',label:'数值存入变量',default:'',varRef:true,showWhen:'match_mode=number_gt,number_lt,number_eq'},
                        auto_stop:{type:'bool',label:'触发后自动停止',default:true} }},
                'monitor/monitor_timer': { display_name: '定时器', color: '#06b6d4', category: 'monitor', icon: 'fa-solid fa-stopwatch',
                    inputs: [], outputs: [{name:'trigger',type:'flow'}],
                    params_schema: { interval:{type:'number',label:'触发间隔',default:1000,varRef:true}, repeat_count:{type:'number',label:'重复次数',default:0,varRef:true},
                        on_trigger:{type:'enum',label:'触发行为',default:'branch',options:['branch','stop_all']} }},
                'variable/var_set': { display_name: '设置变量', color: '#f97316', category: 'variable', icon: 'fa-solid fa-equals',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { vars_json:{type:'var_list',label:'变量列表',default:'[]'},
                        name:{type:'string',label:'变量名(单)',default:''}, value:{type:'string',label:'值(单)',default:'',varRef:true},
                        var_type:{type:'enum',label:'类型(单)',default:'string',options:['number','string','boolean']} }},
                  'variable/var_math': { display_name: '数学运算', color: '#f97316', category: 'variable', icon: 'fa-solid fa-calculator',
                    inputs: [{name:'in',type:'flow'},{name:'A',type:'number'},{name:'B',type:'number'}], outputs: [{name:'next',type:'flow'},{name:'result',type:'number'}],
                    params_schema: { op:{type:'enum',label:'运算',default:'+',options:['+','-','*','/','%','min','max','abs','round']},
                        a:{type:'string',label:'操作数A',default:''}, b:{type:'string',label:'操作数B',default:''}, store_var:{type:'string',label:'存入变量',default:''} }},
                'variable/var_compare': { display_name: '比较', color: '#f97316', category: 'variable', icon: 'fa-solid fa-not-equal',
                    inputs: [{name:'in',type:'flow'},{name:'A',type:'number'},{name:'B',type:'number'}], outputs: [{name:'next',type:'flow'},{name:'result',type:'boolean'}],
                    params_schema: { op:{type:'enum',label:'比较',default:'>',options:['>','<','>=','<=','==','!=']},
                        a:{type:'string',label:'值A',default:''}, b:{type:'string',label:'值B',default:''} }},
                'variable/var_string': { display_name: '字符串操作', color: '#f97316', category: 'variable', icon: 'fa-solid fa-text-width',
                    inputs: [{name:'in',type:'flow'},{name:'str',type:'string'}], outputs: [{name:'next',type:'flow'},{name:'result',type:'string'}],
                    params_schema: { op:{type:'enum',label:'操作',default:'concat',options:['concat','substr','replace','split','regex_extract']},
                        a:{type:'string',label:'输入A',default:''}, b:{type:'string',label:'参数B',default:''}, store_var:{type:'string',label:'存入变量',default:''} }},
                'variable/var_convert': { display_name: '类型转换', color: '#f97316', category: 'variable', icon: 'fa-solid fa-arrow-right-arrow-left',
                    inputs: [{name:'in',type:'flow'},{name:'val',type:'any'}], outputs: [{name:'next',type:'flow'},{name:'result',type:'any'}],
                    params_schema: { to_type:{type:'enum',label:'目标类型',default:'number',options:['number','string','boolean']},
                        input_var:{type:'string',label:'输入变量',default:''}, store_var:{type:'string',label:'存入变量',default:''} }},
                'action/mouse_move': { display_name: '鼠标移动', color: '#22c55e', category: 'action', icon: 'fa-solid fa-up-down-left-right',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { mode:{type:'enum',label:'坐标模式',default:'screen',options:['screen','window','relative']},
                        x:{type:'number',label:'X',default:0,coordRef:true,varRef:true}, y:{type:'number',label:'Y',default:0,coordRef:true,varRef:true},
                        hwnd_var:{type:'string',label:'窗口变量',default:'',varRef:true},
                        duration:{type:'number',label:'移动耗时',default:200,varRef:true},
                        easing:{type:'enum',label:'缓动',default:'ease_in_out',options:['linear','ease_in_out','ease_in','ease_out']} }},
                'action/mouse_move_rel': { display_name: '相对位移', color: '#22c55e', category: 'action', icon: 'fa-solid fa-arrows-up-down-left-right',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { dx:{type:'number',label:'DX',default:100,varRef:true}, dy:{type:'number',label:'DY',default:0,varRef:true},
                        duration:{type:'number',label:'移动耗时',default:200,varRef:true} }},
                'detection/check_image': { display_name: '图像匹配', color: '#eab308', category: 'detection', icon: 'fa-solid fa-image',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'match',type:'flow'},{name:'no',type:'flow'},{name:'result',type:'boolean'},{name:'match_x',type:'number'},{name:'match_y',type:'number'}],
                    params_schema: { mode:{type:'enum',label:'坐标模式',default:'screen',options:['screen','window','relative'],coordMode:true},
                        rect:{type:'region',label:'搜索区域',default:[0,0,0,0],coordMode:true,varRef:true}, hwnd_var:{type:'string',label:'窗口变量',default:'',varRef:true},
                        template_path:{type:'path',label:'模板图片',default:'',browseType:'template'},
                        threshold:{type:'number',label:'匹配阈值',default:0.8,varRef:true},
                        method:{type:'enum',label:'匹配方法',default:'tm_ccoeff_normed',options:['tm_ccoeff_normed','tm_ccorr_normed','tm_sqdiff_normed']},
                        multi_match:{type:'bool',label:'多目标匹配',default:false},
                        store_var:{type:'string',label:'位置变量',default:'',varRef:true} }},
                'detection/check_screen': { display_name: '屏幕状态', color: '#eab308', category: 'detection', icon: 'fa-solid fa-display',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'match',type:'flow'},{name:'no',type:'flow'},{name:'result',type:'boolean'}],
                    params_schema: { state:{type:'enum',label:'检测状态',default:'black',options:['black','bright','frozen']},
                        threshold:{type:'number',label:'亮度阈值',default:30,varRef:true},
                        region:{type:'region',label:'检测区域',default:[0,0,0,0],varRef:true} }},
                'control/wait_cond': { display_name: '等待条件', color: '#a855f7', category: 'control', icon: 'fa-solid fa-clock',
                    inputs: [{name:'in',type:'flow'},{name:'cond',type:'boolean'}],
                    outputs: [{name:'met',type:'flow'},{name:'timeout',type:'flow'}],
                    params_schema: { timeout:{type:'number',label:'超时(ms)',default:10000,varRef:true},
                        interval:{type:'number',label:'检查间隔(ms)',default:100,varRef:true} }},
                'control/goto': { display_name: '跳转', color: '#a855f7', category: 'control', icon: 'fa-solid fa-forward-fast',
                    inputs: [{name:'in',type:'flow'}], outputs: [],
                    params_schema: { target_node_id:{type:'string',label:'目标节点ID',default:''} }},
                'control/seq_check': { display_name: '序列检测', color: '#a855f7', category: 'control', icon: 'fa-solid fa-list-check',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'pass',type:'flow'},{name:'fail',type:'flow'}],
                    params_schema: { steps:{type:'string',label:'步骤描述',default:''},
                        retry:{type:'bool',label:'失败重试',default:true},
                        max_retries:{type:'number',label:'最大重试',default:100} }},
                'control/state_machine': { display_name: '状态机', color: '#a855f7', category: 'control', icon: 'fa-solid fa-circle-nodes',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'done',type:'flow'}],
                    params_schema: { states:{type:'string',label:'状态列表',default:''},
                        fail_state:{type:'string',label:'失败回退',default:''} }},
                'preset/preset_click': { display_name: '点击坐标', color: '#f472b6', category: 'preset', icon: 'fa-solid fa-bullseye',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { mode:{type:'enum',label:'坐标模式',default:'screen',options:['screen','window','relative']},
                        x:{type:'number',label:'X',default:960,coordRef:true,varRef:true}, y:{type:'number',label:'Y',default:540,coordRef:true,varRef:true},
                        hwnd_var:{type:'string',label:'窗口变量',default:'',varRef:true},
                        button:{type:'enum',label:'按键',default:'left',options:['left','right']},
                        move_duration:{type:'number',label:'移动耗时',default:150,varRef:true} }},
                'preset/preset_find_click': { display_name: '找图点击', color: '#f472b6', category: 'preset', icon: 'fa-solid fa-crosshairs',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'found',type:'flow'},{name:'not_found',type:'flow'}],
                    params_schema: { mode:{type:'enum',label:'坐标模式',default:'screen',options:['screen','window','relative'],coordMode:true},
                        rect:{type:'region',label:'搜索区域',default:[0,0,0,0],coordMode:true,varRef:true}, hwnd_var:{type:'string',label:'窗口变量',default:'',varRef:true},
                        template_path:{type:'string',label:'模板图片',default:'',browseType:'template'},
                        threshold:{type:'number',label:'匹配阈值',default:0.8,varRef:true},
                        button:{type:'enum',label:'按键',default:'left',options:['left','right']} }},
                'preset/preset_read_text': { display_name: '读取数字文本', color: '#f472b6', category: 'preset', icon: 'fa-solid fa-hashtag',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { mode:{type:'enum',label:'坐标模式',default:'screen',options:['screen','window','relative'],coordMode:true},
                        rect:{type:'region',label:'检测区域',default:[0,0,100,30],coordMode:true,varRef:true}, hwnd_var:{type:'string',label:'窗口变量',default:'',varRef:true},
                        read_mode:{type:'enum',label:'读取模式',default:'all',options:['all','number','text']},
                        engine:{type:'enum',label:'OCR引擎',default:'rapidocr',options:['rapidocr']},
                        store_var:{type:'string',label:'存入变量',default:'',varRef:true} }},
                'utility/const_number': { display_name: '数字常量', color: '#d8d8d8ff', category: 'utility', icon: 'fa-solid fa-hashtag',
                    inputs: [], outputs: [{name:'value',type:'number'}],
                    params_schema: { value:{type:'number',label:'值',default:0} }},
                'utility/const_string': { display_name: '字符串常量', color: '#d8d8d8ff', category: 'utility', icon: 'fa-solid fa-quote-right',
                    inputs: [], outputs: [{name:'value',type:'string'}],
                    params_schema: { value:{type:'string',label:'值',default:''} }},
                'utility/const_bool': { display_name: '布尔常量', color: '#d8d8d8ff', category: 'utility', icon: 'fa-solid fa-toggle-on',
                    inputs: [], outputs: [{name:'value',type:'boolean'}],
                    params_schema: { value:{type:'bool',label:'值',default:true} }},
                'utility/math_op': { display_name: '数学运算', color: '#d8d8d8ff', category: 'utility', icon: 'fa-solid fa-calculator',
                    inputs: [{name:'A',type:'number'},{name:'B',type:'number'}], outputs: [{name:'result',type:'number'}],
                    params_schema: { op:{type:'enum',label:'运算',default:'add',options:['add','sub','mul','div','mod','pow','min','max']},
                        a:{type:'number',label:'A',default:0}, b:{type:'number',label:'B',default:0} }},
                'utility/math_func': { display_name: '数学函数', color: '#d8d8d8ff', category: 'utility', icon: 'fa-solid fa-square-root-variable',
                    inputs: [{name:'x',type:'number'}], outputs: [{name:'result',type:'number'}],
                    params_schema: { func:{type:'enum',label:'函数',default:'abs',options:['abs','round','floor','ceil','sqrt','sin','cos','log','negate']},
                        x:{type:'number',label:'x',default:0} }},
                'utility/logic_op': { display_name: '逻辑运算', color: '#d8d8d8ff', category: 'utility', icon: 'fa-solid fa-code-merge',
                    inputs: [{name:'A',type:'boolean'},{name:'B',type:'boolean'}], outputs: [{name:'result',type:'boolean'}],
                    params_schema: { op:{type:'enum',label:'运算',default:'and',options:['and','or','xor','not','nand','nor']},
                        a:{type:'bool',label:'A',default:true}, b:{type:'bool',label:'B',default:true} }},
                'utility/compare': { display_name: '数值比较', color: '#d8d8d8ff', category: 'utility', icon: 'fa-solid fa-not-equal',
                    inputs: [{name:'A',type:'number'},{name:'B',type:'number'}], outputs: [{name:'result',type:'boolean'}],
                    params_schema: { op:{type:'enum',label:'比较',default:'gt',options:['eq','ne','gt','lt','ge','le']},
                        a:{type:'number',label:'A',default:0}, b:{type:'number',label:'B',default:0} }},
                'utility/string_op': { display_name: '字符串操作', color: '#d8d8d8ff', category: 'utility', icon: 'fa-solid fa-font',
                    inputs: [{name:'str',type:'string'}], outputs: [{name:'result',type:'string'}],
                    params_schema: { op:{type:'enum',label:'操作',default:'concat',options:['concat','replace','upper','lower','trim','substring','split_index']},
                        input_str:{type:'string',label:'输入',default:''}, param_a:{type:'string',label:'参数A',default:''},
                        param_b:{type:'string',label:'参数B',default:''}, param_c:{type:'string',label:'参数C',default:''} }},
                'utility/condition': { display_name: '条件选择', color: '#d8d8d8ff', category: 'utility', icon: 'fa-solid fa-code-branch',
                    inputs: [{name:'cond',type:'boolean'},{name:'if_true',type:'any'},{name:'if_false',type:'any'}], outputs: [{name:'result',type:'any'}],
                    params_schema: { cond_var:{type:'string',label:'条件变量',default:''},
                        true_val:{type:'string',label:'真值',default:''}, false_val:{type:'string',label:'假值',default:''} }},
                'utility/delay': { display_name: '延迟', color: '#d8d8d8ff', category: 'utility', icon: 'fa-solid fa-hourglass-half',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: { ms:{type:'number',label:'延迟(ms)',default:1000} }},
                'utility/bookmark': { display_name: '坐标书签', color: '#d8d8d8ff', category: 'utility', icon: 'fa-solid fa-bookmark',
                    inputs: [], outputs: [{name:'x',type:'number'},{name:'y',type:'number'},{name:'w',type:'number'},{name:'h',type:'number'}],
                    params_schema: { name:{type:'string',label:'书签名称',default:''}, mode:{type:'enum',label:'坐标模式',default:'screen',options:['screen','window','relative']},
                        x:{type:'number',label:'X坐标',default:0,pickable:true}, y:{type:'number',label:'Y坐标',default:0,pickable:true},
                        w:{type:'number',label:'宽度',default:0,pickable:true}, h:{type:'number',label:'高度',default:0,pickable:true},
                        hwnd_var:{type:'string',label:'窗口句柄',default:''}, remark:{type:'string',label:'备注',default:''} }},
                'flow/start': { display_name: '开始', color: '#99ff00ff', category: 'flow', icon: 'fa-solid fa-play',
                    inputs: [], outputs: [{name:'next',type:'flow'}],
                    params_schema: {} },
                'flow/end': { display_name: '结束', color: '#ef4444', category: 'flow', icon: 'fa-solid fa-stop',
                    inputs: [{name:'in',type:'flow'}], outputs: [],
                    params_schema: {} },
                'plugin/notify': { display_name: '消息提示', color: '#a855f7', category: 'plugin', icon: 'fa-solid fa-bell',
                    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
                    params_schema: {
                        title:{type:'string',label:'标题',default:'提示',varRef:true},
                        message:{type:'string',label:'内容',default:'操作完成',varRef:true},
                        sound:{type:'enum',label:'音效',default:'default',options:['default','info','success','warning','error','none']},
                        duration:{type:'number',label:'显示时长(ms)',default:3000},
                        position:{type:'enum',label:'位置',default:'bottom-right',options:['bottom-right','bottom-left','top-right','top-left','center']}
                    }
                },
            };

            var catNames = { action:'动作节点', detection:'检测节点', control:'控制节点', script_block:'动作块', monitor:'监视器', variable:'变量', preset:'预设', utility:'工具', flow:'流程', plugin:'插件' };
            var catColors = { action:'#22c55e', detection:'#eab308', control:'#a855f7', script_block:'#3b82f6', monitor:'#06b6d4', variable:'#f97316', preset:'#f472b6', utility:'#d8d8d8ff', flow:'#ff0000ff', plugin:'#a855f7' };

            for (var type in fallbackDefs) {
                if (!fallbackDefs.hasOwnProperty(type)) continue;
                var def = fallbackDefs[type];
                this._nodeDefs[type] = def;
                var cat = def.category;
                if (!this._categories[cat]) {
                    this._categories[cat] = { name: catNames[cat] || cat, color: catColors[cat] || '#888', nodes: [] };
                }
                this._categories[cat].nodes.push({ type: type, name: def.display_name, icon: def.icon || '' });
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
        }
    };

export const AutomationNodes = window.AutomationNodes;
