document.addEventListener('DOMContentLoaded', function () {
  var url = '/assets/chi.png + Date.now();

  // Try to find an existing hero container or the .sky wrapper
  var host = document.querySelector('.sky') || document.querySelector('#hero') || document.body;

  // Reuse an existing <img> inside, else create one
  var img = host && host.querySelector('img');
  if (!img) {
    img = new Image();
    img.alt = 'Howard';
    if (host) host.insertBefore(img, host.firstChild);
  }

  if (img) {
    img.src = url;
    img.style.maxWidth = '100%';
    img.style.height = 'auto';
    img.style.objectFit = 'cover';
  }
});
