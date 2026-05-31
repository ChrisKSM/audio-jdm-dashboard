(function () {
  var base = window.__BASE_PATH__ || '/';
  var appUrl = base + 'static/app.jsx';

  function showError(message) {
    var root = document.getElementById('root');
    if (root) {
      root.innerHTML =
        '<div style="padding:24px;color:#b91c1c;font-family:Inter,sans-serif">' +
        '<strong>app.jsx 로드 실패</strong><br><span style="font-size:14px">' +
        message +
        '</span></div>';
    }
    console.error('[bootstrap]', message);
  }

  console.info('[bootstrap] loading', appUrl);

  fetch(appUrl)
    .then(function (response) {
      if (!response.ok) {
        throw new Error(appUrl + ' HTTP ' + response.status);
      }
      return response.text();
    })
    .then(function (code) {
      if (!window.Babel || !window.React || !window.ReactDOM) {
        throw new Error('React/Babel vendor 스크립트가 로드되지 않았습니다.');
      }
      var compiled = Babel.transform(code, {
        presets: ['react'],
        filename: 'app.jsx',
      }).code;
      var script = document.createElement('script');
      script.text = compiled;
      document.body.appendChild(script);
      console.info('[bootstrap] app.jsx loaded');
    })
    .catch(function (error) {
      showError(error.message || String(error));
    });
})();
