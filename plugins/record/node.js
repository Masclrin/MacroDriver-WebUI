var nodes = {
  'plugin/record_start': {
    display_name: '开始录制',
    color: '#8b5cf6',
    category: 'plugin',
    icon: 'fa-solid fa-circle',
    backendAction: 'record_start',
    inputs: [{name:'in', type:'flow'}],
    outputs: [
      {name:'next', type:'flow'},
      {name:'success', type:'data_bool'},
    ],
    params_schema: {
      host:       {type:'string', label:'OBS地址', default:'localhost',
                   description:'OBS WebSocket服务器地址'},
      port:       {type:'number', label:'端口', default:4455,
                   description:'OBS WebSocket端口'},
      password:   {type:'string', label:'密码', default:'',
                   description:'OBS WebSocket密码(无密码则留空)'},
      fps:        {type:'number', label:'帧率', default:30,
                   description:'录制帧率，建议15-60'},
      record_format: {type:'enum', label:'录制格式', default:'mp4',
                     options:['mp4','mkv','flv','mov']},
      save_dir:   {type:'string', label:'保存目录', default:'',
                   description:'留空使用OBS默认目录'},
      filename:   {type:'string', label:'文件名', default:'record_${timestamp}',
                   description:'支持 ${timestamp} 变量'}
    },
    onExecute: function(params) {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.call_plugin) {
        window.pywebview.api.call_plugin('record', 'record_start', params).then(function(res) {
          if (res && res.ok) {
            if (window._autoEditor && window._autoEditor.showToast) {
              window._autoEditor.showToast('OBS录屏已启动', 'ok');
            }
          } else {
            var errMsg = (res && res.error) || '启动录屏失败';
            if (window._autoEditor && window._autoEditor.showToast) {
              window._autoEditor.showToast(errMsg, 'err');
            }
          }
        }).catch(function(err) {
          if (window._autoEditor && window._autoEditor.showToast) {
            window._autoEditor.showToast('录屏异常: ' + (err.message || err), 'err');
          }
        });
      }
    }
  },
  'plugin/record_stop': {
    display_name: '停止录制',
    color: '#8b5cf6',
    category: 'plugin',
    icon: 'fa-solid fa-square',
    backendAction: 'record_stop',
    inputs: [{name:'in', type:'flow'}],
    outputs: [
      {name:'next', type:'flow'},
      {name:'success', type:'data_bool'},
      {name:'filepath', type:'data_string'},
    ],
    params_schema: {
      host:       {type:'string', label:'OBS地址', default:'localhost'},
      port:       {type:'number', label:'端口', default:4455},
      password:   {type:'string', label:'密码', default:''},
      filename:   {type:'string', label:'文件名', default:'record_${timestamp}',
                   description:'支持 ${timestamp} 变量'},
      stop_buffer: {type:'bool', label:'停止回放缓冲', default:false,
                    description:'保存后是否关闭后台录制'},
      store_var:  {type:'string', label:'路径存入变量', default:'record_path',
                   description:'录屏文件路径存入此变量，方便邮件插件引用'}
    },
    onExecute: function(params) {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.call_plugin) {
        window.pywebview.api.call_plugin('record', 'record_stop', params).then(function(res) {
          if (res && res.ok) {
            var path = res.data && res.data.filepath || params.store_var;
            if (window._autoEditor && window._autoEditor.showToast) {
              window._autoEditor.showToast('录屏已保存: ' + path, 'ok');
            }
          } else {
            var errMsg = (res && res.error) || '停止录屏失败';
            if (window._autoEditor && window._autoEditor.showToast) {
              window._autoEditor.showToast(errMsg, 'err');
            }
          }
        }).catch(function(err) {
          if (window._autoEditor && window._autoEditor.showToast) {
            window._autoEditor.showToast('录屏异常: ' + (err.message || err), 'err');
          }
        });
      }
    }
  }
};
window.__plugin_nodes__ = nodes;