var nodes = {
  'plugin/email_send': {
    display_name: '发送邮件',
    color: '#3b82f6',
    category: 'plugin',
    icon: 'fa-solid fa-envelope',
    backendAction: 'send_email',
    inputs: [{name:'in', type:'flow'}],
    outputs: [
      {name:'next', type:'flow'},
      {name:'success', type:'data_bool'},
      {name:'error_message', type:'data_string'},
    ],
    params_schema: {
      smtp_host:    {type:'string', label:'SMTP服务器', default:'smtp.qq.com'},
      smtp_port:    {type:'number', label:'端口', default:465},
      use_ssl:      {type:'bool', label:'SSL', default:true},
      username:     {type:'string', label:'发件邮箱', default:''},
      password:     {type:'string', label:'授权码/密码', default:''},
      to:           {type:'string', label:'收件人', default:'', varRef:true, description:'多个收件人用逗号分隔'},
      cc:           {type:'string', label:'抄送', default:'', varRef:true},
      subject:      {type:'string', label:'主题', default:'通知', varRef:true},
      body:         {type:'string', label:'正文', default:'', varRef:true},
      html:         {type:'bool', label:'HTML正文', default:false},
      attachments:  {type:'string', label:'附件路径', default:'', varRef:true, description:'文件路径，多个用分号分隔，支持变量如 ${screenshot_path}'},
      attachment_dir: {type:'string', label:'附件目录', default:'', varRef:true, description:'发送该目录下所有文件'},
      attachment_pattern: {type:'string', label:'文件名匹配', default:'', varRef:true, description:'附件目录中的文件名模式，如 screenshot_*.png'}
    },
    onExecute: function(params) {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.call_plugin) {
        window.pywebview.api.call_plugin('email', 'send_email', params).then(function(res) {
          if (res && res.ok) {
            if (window._autoEditor && window._autoEditor.showToast) {
              window._autoEditor.showToast('邮件发送成功', 'ok');
            }
          } else {
            var errMsg = (res && res.error) || '邮件发送失败';
            if (window._autoEditor && window._autoEditor.showToast) {
              window._autoEditor.showToast(errMsg, 'err');
            }
          }
        }).catch(function(err) {
          if (window._autoEditor && window._autoEditor.showToast) {
            window._autoEditor.showToast('邮件发送异常: ' + (err.message || err), 'err');
          }
        });
      }
    }
  }
};
window.__plugin_nodes__ = nodes;
