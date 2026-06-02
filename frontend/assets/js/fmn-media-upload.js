/* ============================================================================
 * fmn-media-upload.js  —  FindMyNyumba media uploader
 * Drag&drop + click + multi-select; photo/video previews; client validation
 * (max 20, jpg/jpeg/png/webp + mp4/mov/webm, 10MB photo / 100MB video);
 * remove + drag-to-reorder; real upload progress via XHR.
 * Sends files under the multipart field name "media" (backend Option B).
 * Branding: FMN orange (#ea580c), rounded-xl, FontAwesome. No dependencies.
 * ========================================================================== */
(function (global) {
  'use strict';
  var MAX_FILES = 20;
  var MAX_PHOTO = 10 * 1024 * 1024;
  var MAX_VIDEO = 100 * 1024 * 1024;
  var FIELD_NAME = 'media';
  var PHOTO_EXT = { jpg:1, jpeg:1, png:1, webp:1 };
  var VIDEO_EXT = { mp4:1, mov:1, webm:1 };
  var PHOTO_MIME = { 'image/jpeg':1, 'image/png':1, 'image/webp':1 };
  var VIDEO_MIME = { 'video/mp4':1, 'video/quicktime':1, 'video/webm':1 };
  var ACCEPT = 'image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm,.jpg,.jpeg,.png,.webp,.mp4,.mov,.webm';
  var _seq = 0;

  function ext(n){ return n.indexOf('.')===-1 ? '' : n.split('.').pop().toLowerCase(); }
  function fmtSize(b){ return b>=1048576 ? (b/1048576).toFixed(1)+' MB' : Math.max(1,Math.round(b/1024))+' KB'; }
  function fmtDur(s){ if(!isFinite(s)||s<=0) return ''; var m=Math.floor(s/60),x=Math.round(s%60); return m+':'+String(x).padStart(2,'0'); }
  function classify(f){ var e=ext(f.name), t=(f.type||'').toLowerCase();
    if(PHOTO_MIME[t]||PHOTO_EXT[e]) return 'photo';
    if(VIDEO_MIME[t]||VIDEO_EXT[e]) return 'video';
    return null; }

  function FMNMediaUpload(container, opts){
    opts = opts || {};
    this.maxFiles = opts.maxFiles || MAX_FILES;
    this.fieldName = opts.fieldName || FIELD_NAME;
    this.items = [];
    this._dragId = null;
    this._build(container);
  }

  FMNMediaUpload.prototype._build = function(container){
    var self=this;
    container.innerHTML =
      '<div class="fmn-mu">' +
      '  <div class="fmn-mu-drop" tabindex="0" role="button" aria-label="Add photos or videos">' +
      '    <i class="fas fa-cloud-upload-alt fmn-mu-cloud"></i>' +
      '    <p class="fmn-mu-title">Drop photos &amp; videos here</p>' +
      '    <p class="fmn-mu-sub">or <span class="fmn-mu-link">browse</span> &middot; up to '+self.maxFiles+' files</p>' +
      '    <p class="fmn-mu-hint">JPG, PNG, WEBP &middot; MP4, MOV, WEBM</p>' +
      '    <input type="file" class="fmn-mu-input" multiple accept="'+ACCEPT+'" hidden>' +
      '  </div>' +
      '  <div class="fmn-mu-err" hidden></div>' +
      '  <div class="fmn-mu-bar" hidden><div class="fmn-mu-bar-fill"></div><span class="fmn-mu-bar-pct">0%</span></div>' +
      '  <div class="fmn-mu-grid"></div>' +
      '  <div class="fmn-mu-count"></div>' +
      '</div>';
    this.root=container.querySelector('.fmn-mu');
    this.drop=container.querySelector('.fmn-mu-drop');
    this.input=container.querySelector('.fmn-mu-input');
    this.errEl=container.querySelector('.fmn-mu-err');
    this.grid=container.querySelector('.fmn-mu-grid');
    this.countEl=container.querySelector('.fmn-mu-count');
    this.barEl=container.querySelector('.fmn-mu-bar');
    this.barFill=container.querySelector('.fmn-mu-bar-fill');
    this.barPct=container.querySelector('.fmn-mu-bar-pct');
    FMNMediaUpload._injectStyle();

    this.drop.addEventListener('click', function(){ self.input.click(); });
    this.drop.addEventListener('keydown', function(e){ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); self.input.click(); } });
    this.input.addEventListener('change', function(){ self.add(this.files); this.value=''; });
    ['dragenter','dragover'].forEach(function(ev){ self.drop.addEventListener(ev,function(e){ e.preventDefault(); self.drop.classList.add('is-over'); }); });
    ['dragleave','drop'].forEach(function(ev){ self.drop.addEventListener(ev,function(e){ e.preventDefault(); self.drop.classList.remove('is-over'); }); });
    this.drop.addEventListener('drop', function(e){ if(e.dataTransfer&&e.dataTransfer.files) self.add(e.dataTransfer.files); });
    this._render();
  };

  FMNMediaUpload.prototype.add = function(fileList){
    var errs=[], files=Array.prototype.slice.call(fileList||[]);
    for(var i=0;i<files.length;i++){
      var file=files[i];
      if(this.items.length>=this.maxFiles){ errs.push('Maximum '+this.maxFiles+' files reached.'); break; }
      var kind=classify(file);
      if(!kind){ errs.push('\u201c'+file.name+'\u201d is not a supported photo or video.'); continue; }
      var cap=kind==='photo'?MAX_PHOTO:MAX_VIDEO;
      if(file.size>cap){ errs.push('\u201c'+file.name+'\u201d is too large ('+fmtSize(file.size)+'). Max '+(cap/1048576)+'MB for a '+kind+'.'); continue; }
      if(this.items.some(function(it){ return it.file.name===file.name && it.file.size===file.size; })) continue;
      this.items.push({ id:++_seq, file:file, kind:kind, url:URL.createObjectURL(file) });
    }
    this._showErrors(errs); this._render();
  };

  FMNMediaUpload.prototype.remove = function(id){
    var i=this.items.findIndex(function(it){ return it.id===id; });
    if(i>-1){ URL.revokeObjectURL(this.items[i].url); this.items.splice(i,1); this._render(); }
  };

  FMNMediaUpload.prototype._reorder = function(fromId, toId){
    if(fromId===toId) return;
    var from=this.items.findIndex(function(it){return it.id===fromId;});
    var to=this.items.findIndex(function(it){return it.id===toId;});
    if(from<0||to<0) return;
    var moved=this.items.splice(from,1)[0];
    this.items.splice(to,0,moved);
    this._render();
  };

  FMNMediaUpload.prototype._render = function(){
    var self=this; this.grid.innerHTML='';
    var firstPhotoSeen=false;
    this.items.forEach(function(it,index){
      var card=document.createElement('div');
      card.className='fmn-mu-card'; card.setAttribute('draggable','true'); card.dataset.id=it.id;
      var media = it.kind==='photo'
        ? '<img class="fmn-mu-thumb" src="'+it.url+'" alt="">'
        : '<video class="fmn-mu-thumb" src="'+it.url+'#t=0.1" muted playsinline preload="metadata"></video>' +
          '<span class="fmn-mu-play"><i class="fas fa-play"></i></span><span class="fmn-mu-dur"></span>';
      var isCover = it.kind==='photo' && !firstPhotoSeen;
      if(isCover) firstPhotoSeen=true;
      card.innerHTML =
        '<div class="fmn-mu-media">'+media+
          (isCover?'<span class="fmn-mu-cover">Cover</span>':'')+
          '<button type="button" class="fmn-mu-del" aria-label="Remove"><i class="fas fa-times"></i></button>'+
        '</div>'+
        '<p class="fmn-mu-name" title="'+it.file.name+'">'+it.file.name+'</p>'+
        '<p class="fmn-mu-meta"><i class="fas fa-'+(it.kind==='photo'?'image':'film')+'"></i> '+fmtSize(it.file.size)+'</p>';
      card.querySelector('.fmn-mu-del').addEventListener('click', function(e){ e.stopPropagation(); self.remove(it.id); });
      if(it.kind==='video'){
        var v=card.querySelector('video');
        v.addEventListener('loadedmetadata', function(){ var d=card.querySelector('.fmn-mu-dur'); if(d) d.textContent=fmtDur(v.duration); try{ v.currentTime=Math.min(0.1, v.duration||0.1); }catch(_){ } });
      }
      // drag-to-reorder
      card.addEventListener('dragstart', function(){ self._dragId=it.id; card.classList.add('is-dragging'); });
      card.addEventListener('dragend', function(){ self._dragId=null; card.classList.remove('is-dragging'); });
      card.addEventListener('dragover', function(e){ e.preventDefault(); });
      card.addEventListener('drop', function(e){ e.preventDefault(); if(self._dragId!=null) self._reorder(self._dragId, it.id); });
      self.grid.appendChild(card);
    });
    this.countEl.textContent = this.items.length ? this.items.length+' / '+this.maxFiles+' files \u00b7 drag to reorder' : '';
    this.root.classList.toggle('has-items', this.items.length>0);
  };

  FMNMediaUpload.prototype._showErrors = function(errs){
    if(errs&&errs.length){ this.errEl.innerHTML='<i class="fas fa-exclamation-circle"></i> '+errs.join('<br>'); this.errEl.hidden=false; }
    else { this.errEl.hidden=true; this.errEl.innerHTML=''; }
  };

  FMNMediaUpload.prototype.count = function(){ return this.items.length; };
  FMNMediaUpload.prototype.appendTo = function(fd, name){ name=name||this.fieldName; this.items.forEach(function(it){ fd.append(name, it.file, it.file.name); }); return fd; };
  FMNMediaUpload.prototype.setOverallProgress = function(pct){
    pct=Math.max(0,Math.min(100,Math.round(pct)));
    this.barEl.hidden=false; this.barFill.style.width=pct+'%'; this.barPct.textContent=pct+'%';
    this.drop.setAttribute('aria-disabled','true');
    if(pct>=100){ var self=this; setTimeout(function(){ self.barEl.hidden=true; self.barFill.style.width='0%'; }, 600); }
  };
  FMNMediaUpload.prototype.reset = function(){
    this.items.forEach(function(it){ URL.revokeObjectURL(it.url); });
    this.items=[]; this.barEl.hidden=true; this.barFill.style.width='0%';
    this.drop.removeAttribute('aria-disabled'); this._showErrors([]); this._render();
  };

  // Turn a FastAPI error body into a human message. 422 `detail` is an array
  // of {loc, msg}; a plain string detail is used as-is.
  FMNMediaUpload._errMsg = function(d, status){
    if (d && typeof d.detail === 'string') return d.detail;
    if (d && Array.isArray(d.detail) && d.detail.length){
      return d.detail.map(function(e){
        var field = Array.isArray(e.loc) ? e.loc[e.loc.length-1] : '';
        var label = String(field).replace(/_/g,' ');
        return (label ? (label.charAt(0).toUpperCase()+label.slice(1)+': ') : '') + (e.msg || 'invalid');
      }).join('  •  ');
    }
    return 'Upload failed (' + status + ').';
  };

  FMNMediaUpload.xhrUpload = function(o){
    return new Promise(function(resolve,reject){
      var xhr=new XMLHttpRequest();
      xhr.open(o.method||'POST', o.url);
      if(o.token) xhr.setRequestHeader('Authorization','Bearer '+o.token);
      xhr.upload.onprogress=function(e){ if(e.lengthComputable&&o.onProgress) o.onProgress((e.loaded/e.total)*100); };
      xhr.onload=function(){ var d={}; try{ d=JSON.parse(xhr.responseText||'{}'); }catch(_){}
        if(xhr.status>=200&&xhr.status<300){ if(o.onProgress) o.onProgress(100); resolve(d); }
        else reject(new Error(FMNMediaUpload._errMsg(d, xhr.status))); };
      xhr.onerror=function(){ reject(new Error('Network error during upload.')); };
      xhr.send(o.formData);
    });
  };

  FMNMediaUpload._injectStyle = function(){
    if(document.getElementById('fmn-mu-style')) return;
    var css =
'.fmn-mu{--mu-orange:#ea580c;--mu-orange-light:#fff7ed;}'+
'.fmn-mu-drop{border:2px dashed #e5e7eb;border-radius:12px;background:#fafafa;padding:26px 16px;text-align:center;cursor:pointer;transition:border-color .15s,background .15s;}'+
'.fmn-mu-drop:hover{border-color:#d4d4d8;background:#f7f7f8;}'+
'.fmn-mu-drop:focus-visible{outline:none;border-color:var(--mu-orange);}'+
'.fmn-mu-drop.is-over{border-color:var(--mu-orange);background:var(--mu-orange-light);}'+
'.fmn-mu-drop[aria-disabled="true"]{opacity:.6;pointer-events:none;}'+
'.fmn-mu-cloud{font-size:26px;color:var(--mu-orange);margin-bottom:8px;}'+
'.fmn-mu-title{font-weight:800;color:#374151;font-size:14px;margin:0;}'+
'.fmn-mu-sub{font-size:12.5px;color:#6b7280;margin:3px 0 0;}'+
'.fmn-mu-link{color:var(--mu-orange);font-weight:700;text-decoration:underline;}'+
'.fmn-mu-hint{font-size:11px;color:#9ca3af;margin:6px 0 0;letter-spacing:.02em;}'+
'.fmn-mu-err{margin-top:10px;padding:10px 12px;background:#fef2f2;border:1px solid #fecaca;color:#dc2626;font-size:12.5px;border-radius:10px;line-height:1.5;}'+
'.fmn-mu-err i{margin-right:4px;}'+
'.fmn-mu-bar{position:relative;height:10px;background:#f3f4f6;border-radius:999px;margin-top:12px;overflow:hidden;}'+
'.fmn-mu-bar-fill{height:100%;width:0;background:var(--mu-orange);border-radius:999px;transition:width .2s ease;}'+
'.fmn-mu-bar-pct{position:absolute;right:8px;top:-18px;font-size:11px;font-weight:700;color:var(--mu-orange);}'+
'.fmn-mu-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:12px;margin-top:14px;}'+
'.fmn-mu-grid:empty{margin-top:0;}'+
'.fmn-mu-card{font-size:12px;cursor:grab;}'+
'.fmn-mu-card.is-dragging{opacity:.4;}'+
'.fmn-mu-media{position:relative;width:100%;aspect-ratio:1/1;border-radius:10px;overflow:hidden;background:#0b0b0c;border:1px solid #ececed;}'+
'.fmn-mu-thumb{width:100%;height:100%;object-fit:cover;display:block;}'+
'.fmn-mu-play{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:#fff;font-size:18px;text-shadow:0 1px 4px rgba(0,0,0,.5);pointer-events:none;}'+
'.fmn-mu-dur{position:absolute;bottom:6px;right:6px;background:rgba(0,0,0,.7);color:#fff;font-size:10.5px;font-weight:700;padding:1px 6px;border-radius:6px;}'+
'.fmn-mu-cover{position:absolute;top:6px;left:6px;background:var(--mu-orange);color:#fff;font-size:10px;font-weight:800;letter-spacing:.03em;text-transform:uppercase;padding:2px 7px;border-radius:6px;}'+
'.fmn-mu-del{position:absolute;top:6px;right:6px;width:24px;height:24px;border:none;border-radius:50%;background:rgba(0,0,0,.6);color:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:11px;transition:background .15s;}'+
'.fmn-mu-del:hover{background:#dc2626;}'+
'.fmn-mu-name{margin:6px 0 0;font-weight:700;color:#374151;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}'+
'.fmn-mu-meta{margin:1px 0 0;color:#9ca3af;font-size:11px;}'+
'.fmn-mu-meta i{margin-right:2px;}'+
'.fmn-mu-count{margin-top:10px;font-size:11.5px;font-weight:700;color:#9ca3af;text-align:right;}';
    var tag=document.createElement('style'); tag.id='fmn-mu-style'; tag.textContent=css; document.head.appendChild(tag);
  };

  global.FMNMediaUpload = FMNMediaUpload;
})(window);
