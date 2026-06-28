var nodes = {
  'plugin/screenshot_capture': {
    display_name: '截图保存',
    color: '#22c55e',
    category: 'plugin',
    icon: 'fa-solid fa-camera',
    backendAction: 'capture',
    inputs: [{name:'in', type:'flow'}],
    outputs: [{name:'next', type:'flow'}],
    params_schema: {
      mode:         {type:'enum', label:'坐标模式', default:'screen',
                     options:['screen','window','relative'], coordMode:true},
      capture_mode: {type:'enum', label:'截图方式', default:'fullscreen',
                     options:['fullscreen','region','window']},
      rect:         {type:'region', label:'截图区域', default:[0,0,0,0], coordMode:true,
                     description:'区域截图时有效，[x,y,w,h]'},
      hwnd_var:     {type:'string', label:'窗口变量', default:'', varRef:true,
                     description:'window/relative模式需要指定窗口句柄'},
      save_dir:     {type:'string', label:'保存目录', default:'', varRef:true,
                     description:'留空则保存到临时目录'},
      filename:     {type:'string', label:'文件名', default:'screenshot_${timestamp}', varRef:true,
                     description:'支持变量如 ${timestamp}, ${date}, ${counter}'},
      format:       {type:'enum', label:'图片格式', default:'png',
                     options:['png','jpg','bmp']},
      quality:      {type:'number', label:'JPG质量', default:95, varRef:true,
                     description:'仅JPG格式有效，1-100'},
      store_var:    {type:'string', label:'存入变量', default:'screenshot_path',
                     description:'截图文件路径存入此变量，方便邮件插件引用'}
    },
    onExecute: function(params) {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.call_plugin) {
        window.pywebview.api.call_plugin('screenshot', 'capture', params).then(function(res) {
          if (res && res.ok && res.data) {
            if (window._autoEditor && window._autoEditor.showToast) {
              window._autoEditor.showToast('截图已保存: ' + (res.data.filename || ''), 'ok');
            }
          } else {
            var errMsg = (res && res.error) || '截图失败';
            if (window._autoEditor && window._autoEditor.showToast) {
              window._autoEditor.showToast(errMsg, 'err');
            }
          }
        }).catch(function(err) {
          if (window._autoEditor && window._autoEditor.showToast) {
            window._autoEditor.showToast('截图异常: ' + (err.message || err), 'err');
          }
        });
      }
    }
  },
  'plugin/screenshot_ocr': {
    display_name: '截图OCR',
    color: '#22c55e',
    category: 'plugin',
    icon: 'fa-solid fa-language',
    backendAction: 'ocr',
    inputs: [{name:'in', type:'flow'}],
    outputs: [{name:'next', type:'flow'}],
    params_schema: {
      mode:         {type:'enum', label:'坐标模式', default:'screen',
                     options:['screen','window','relative'], coordMode:true},
      capture_mode: {type:'enum', label:'截图方式', default:'region',
                     options:['fullscreen','region','window']},
      rect:         {type:'region', label:'OCR区域', default:[0,0,200,50], coordMode:true},
      hwnd_var:     {type:'string', label:'窗口变量', default:'', varRef:true},
      engine:       {type:'enum', label:'OCR引擎', default:'rapidocr',
                     options:['rapidocr']},
      save_screenshot: {type:'bool', label:'同时保存截图', default:false},
      save_dir:     {type:'string', label:'保存目录', default:'', varRef:true},
      filename:     {type:'string', label:'文件名', default:'ocr_${timestamp}', varRef:true},
      store_text_var: {type:'string', label:'文本存入变量', default:'ocr_text'},
      store_path_var: {type:'string', label:'路径存入变量', default:'screenshot_path'}
    },
    onExecute: function(params) {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.call_plugin) {
        window.pywebview.api.call_plugin('screenshot', 'ocr', params).then(function(res) {
          if (res && res.ok && res.data) {
            if (window._autoEditor && window._autoEditor.showToast) {
              var text = res.data.text || '(空)';
              window._autoEditor.showToast('OCR识别: ' + text.substring(0, 50), 'ok');
            }
          } else {
            var errMsg = (res && res.error) || 'OCR失败';
            if (window._autoEditor && window._autoEditor.showToast) {
              window._autoEditor.showToast(errMsg, 'err');
            }
          }
        }).catch(function(err) {
          if (window._autoEditor && window._autoEditor.showToast) {
            window._autoEditor.showToast('OCR异常: ' + (err.message || err), 'err');
          }
        });
      }
    }
  }
};
window.__plugin_nodes__ = nodes;
