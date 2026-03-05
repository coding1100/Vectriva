(function() {
  'use strict';

  const scripts = document.getElementsByTagName('script');
  const currentScript = scripts[scripts.length - 1];
  const apiKey = currentScript.getAttribute('data-api-key');
  const primaryColor = currentScript.getAttribute('data-color') || '#3B82F6';
  const welcomeMessage = currentScript.getAttribute('data-welcome') || 'Hi! How can I help you today?';
  const position = currentScript.getAttribute('data-position') || 'bottom-right';

  if (!apiKey) {
    console.error('Vectriva: data-api-key attribute is required');
    return;
  }

  const embedUrl = currentScript.src.replace('/embed.js', '');
  const iframeUrl = `${embedUrl}/embed?key=${encodeURIComponent(apiKey)}&color=${encodeURIComponent(primaryColor)}&welcome=${encodeURIComponent(welcomeMessage)}`;

  const container = document.createElement('div');
  container.id = 'vectriva-widget-container';
  container.style.cssText = `
    position: fixed;
    ${position === 'bottom-left' ? 'left: 0;' : 'right: 0;'}
    bottom: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    z-index: 999999;
  `;

  const iframe = document.createElement('iframe');
  iframe.id = 'vectriva-widget-iframe';
  iframe.src = iframeUrl;
  iframe.style.cssText = `
    position: absolute;
    ${position === 'bottom-left' ? 'left: 0;' : 'right: 0;'}
    bottom: 0;
    width: 100%;
    height: 100%;
    border: none;
    pointer-events: auto;
  `;
  iframe.setAttribute('title', 'Vectriva Chat Widget');
  iframe.setAttribute('allowTransparency', 'true');

  container.appendChild(iframe);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      document.body.appendChild(container);
    });
  } else {
    document.body.appendChild(container);
  }

  window.addEventListener('message', function(event) {
    if (event.origin !== embedUrl) return;

    if (event.data.type === 'vectriva-resize') {
      iframe.style.height = event.data.height + 'px';
    }
  });
})();
