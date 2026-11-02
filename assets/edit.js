/* In-page editing for signed-in admins. Every editable text is a span[data-t]; dynamic
   values ({{tokens}}) are chips (span.tok) that stay as they are. Saves to /admin/api/texts. */
(function () {
  "use strict";
  var bar = document.querySelector(".kab");
  if (!bar || bar.getAttribute("data-edit") !== "1") return;

  var root = document.documentElement;
  root.classList.add("kaish-editing");
  var csrf = bar.getAttribute("data-csrf");
  var lang = bar.getAttribute("data-lang");
  var page = bar.getAttribute("data-page");
  var saveBtn = bar.querySelector("[data-save]");
  var state = bar.querySelector("[data-count]");

  // Show everything so it can be edited: closed answers, conditional questions, confirmations.
  document.querySelectorAll("main details").forEach(function (d) { d.open = true; });
  document.querySelectorAll("main [hidden]").forEach(function (el) {
    if (el.matches(".errsum, .hp, .send-error") || el.closest(".hp")) return;
    el.hidden = false;
    el.setAttribute("data-was-hidden", "");
  });

  var plain = (function () {
    var s = document.createElement("span");
    s.contentEditable = "plaintext-only";
    return s.contentEditable === "plaintext-only";
  })();

  function serialize(el) {
    var out = "";
    el.childNodes.forEach(function (n) {
      if (n.nodeType === 3) out += n.nodeValue;
      else if (n.nodeType === 1) {
        if (n.classList.contains("tok")) out += "{{" + n.getAttribute("data-tok") + "}}";
        else if (n.tagName === "BR") out += " ";
        else out += serialize(n);
      }
    });
    return out;
  }
  function clean(s) { return s.replace(/\s+/g, " ").trim(); }

  var spans = Array.prototype.slice.call(document.querySelectorAll("[data-t]"));
  var original = new Map();
  spans.forEach(function (s) {
    s.setAttribute("contenteditable", plain ? "plaintext-only" : "true");
    s.setAttribute("spellcheck", "true");
    original.set(s, clean(serialize(s)));
  });

  var dirty = new Map(); // key -> value
  function refresh() {
    var n = dirty.size;
    state.textContent = n ? n + " unsaved change" + (n === 1 ? "" : "s") : "No unsaved changes";
    state.classList.toggle("dirty", n > 0);
    saveBtn.disabled = n === 0;
  }

  document.addEventListener("input", function (e) {
    var s = e.target.closest && e.target.closest("[data-t]");
    if (!s) return;
    var key = s.getAttribute("data-t"), value = clean(serialize(s));
    // keep copies of the same text (the header menu and the glass bar) in step
    spans.forEach(function (o) {
      if (o !== s && o.getAttribute("data-t") === key && o.textContent !== s.textContent) o.textContent = s.textContent;
    });
    if (value === original.get(s)) { dirty.delete(key); s.classList.remove("changed"); }
    else { dirty.set(key, value); s.classList.add("changed"); }
    refresh();
  });

  // One line per text: Enter saves, Escape leaves the text.
  document.addEventListener("keydown", function (e) {
    if (!e.target.closest || !e.target.closest("[data-t]")) return;
    if (e.key === "Enter") { e.preventDefault(); if (dirty.size) save(); }
    if (e.key === "Escape") e.target.blur();
  });

  // Paste plain text only.
  document.addEventListener("paste", function (e) {
    if (!e.target.closest || !e.target.closest("[data-t]")) return;
    e.preventDefault();
    var text = (e.clipboardData || window.clipboardData).getData("text/plain").replace(/\s+/g, " ");
    document.execCommand("insertText", false, text);
  });

  // While editing, links, buttons and form labels don't act.
  document.addEventListener("click", function (e) {
    if (e.target.closest(".kab, .sec-tog, .plate-tools")) return;
    if (e.target.closest("a, button, label, summary")) e.preventDefault();
  }, true);
  document.addEventListener("submit", function (e) {
    if (!e.target.closest(".kab")) e.preventDefault();
  }, true);

  function save() {
    if (!dirty.size) return;
    saveBtn.disabled = true;
    saveBtn.textContent = "Saving…";
    var changes = [];
    dirty.forEach(function (value, key) { changes.push({ t: key, value: value }); });
    fetch("/admin/api/texts", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
      body: JSON.stringify({ lang: lang, page: page, changes: changes })
    }).then(function (r) { return r.json(); }).then(function (res) {
      if (!res.ok) throw new Error(res.error || "failed");
      spans.forEach(function (s) {
        if (dirty.has(s.getAttribute("data-t"))) { original.set(s, clean(serialize(s))); s.classList.remove("changed"); }
      });
      dirty.clear();
      refresh();
      state.textContent = "Saved";
    }).catch(function () {
      state.textContent = "Couldn't save. Check your connection, or sign in again.";
      state.classList.add("dirty");
      saveBtn.disabled = false;
    }).then(function () { saveBtn.textContent = "Save changes"; });
  }
  saveBtn.addEventListener("click", save);

  // Hide / show any section for visitors. Hidden sections stay visible here, faded.
  var seen = {};
  Array.prototype.slice.call(document.querySelectorAll("[data-sec]")).forEach(function (el) {
    if (el.closest(".glassbar, .kab, [hidden]")) return;
    var scope = el.closest("main") ? page : "layout";
    var key = el.getAttribute("data-sec");
    var id = scope + "|" + key;
    if (seen[id]) return;
    seen[id] = true;
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "sec-tog";
    function label() {
      var off = el.hasAttribute("data-sec-off");
      btn.textContent = off ? "Hidden from visitors · Show" : "Hide";
      btn.setAttribute("aria-label", off ? "Show this section to visitors" : "Hide this section from visitors");
    }
    label();
    if (/^(A|BUTTON)$/.test(el.tagName)) {
      btn.classList.add("sec-tog-inline");
      el.insertAdjacentElement("afterend", btn);
    } else if (/^(LI|P|SPAN)$/.test(el.tagName) || (el.offsetHeight < 56 && /flex/.test(getComputedStyle(el).display))) {
      // small blocks: the button goes at the end of the line instead of covering the text
      btn.classList.add("sec-tog-inline");
      el.appendChild(btn);
    } else {
      if (getComputedStyle(el).position === "static") el.style.position = "relative";
      el.insertBefore(btn, el.firstChild);
    }
    btn.addEventListener("click", function () {
      var hide = !el.hasAttribute("data-sec-off");
      btn.disabled = true;
      fetch("/admin/api/sections", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify({ scope: scope, key: key, hidden: hide })
      }).then(function (r) { return r.json(); }).then(function (res) {
        if (!res.ok) throw new Error(res.error || "failed");
        Array.prototype.slice.call(document.querySelectorAll('[data-sec="' + key + '"]')).forEach(function (other) {
          if ((other.closest("main") ? page : "layout") !== scope) return;
          if (hide) other.setAttribute("data-sec-off", ""); else other.removeAttribute("data-sec-off");
        });
        label();
      }).catch(function () {
        btn.textContent = "Couldn't save. Try again";
      }).then(function () { btn.disabled = false; });
    });
  });

  // The homepage picture (Plate I): upload a new one, or go back to the woven pattern.
  var frame = document.querySelector(".plate-frame");
  if (frame) {
    var tools = document.createElement("div");
    tools.className = "plate-tools";
    tools.innerHTML = '<label class="sec-tog sec-tog-inline plate-pick">Change picture<input type="file" accept="image/jpeg,image/png,image/webp" hidden></label>' +
      '<button type="button" class="sec-tog sec-tog-inline plate-reset">Use the woven pattern</button>' +
      '<span class="plate-msg" role="status"></span>';
    frame.insertAdjacentElement("afterend", tools);
    var input = tools.querySelector("input"), reset = tools.querySelector(".plate-reset"), msg = tools.querySelector(".plate-msg");
    function sync() { reset.hidden = !frame.querySelector("img"); }
    function send(data) {
      data.append("lang", lang);
      msg.textContent = "Saving…";
      fetch("/admin/api/plate", { method: "POST", credentials: "same-origin", headers: { "X-CSRF-Token": csrf }, body: data })
        .then(function (r) { return r.json(); })
        .then(function (res) {
          if (!res.ok) throw new Error(res.error || "failed");
          frame.innerHTML = res.html;
          msg.textContent = res.custom ? "Saved. Now edit the caption below to describe the new picture." : "Saved. The woven pattern is back.";
          sync();
        })
        .catch(function (err) { msg.textContent = (err && err.message && err.message !== "failed") ? err.message : "Couldn't save. Try again."; });
    }
    input.addEventListener("change", function () {
      if (!input.files[0]) return;
      var data = new FormData();
      data.append("picture", input.files[0]);
      send(data);
      input.value = "";
    });
    reset.addEventListener("click", function () {
      var data = new FormData();
      data.append("reset", "1");
      send(data);
    });
    sync();
  }

  window.addEventListener("beforeunload", function (e) {
    if (dirty.size) { e.preventDefault(); e.returnValue = ""; }
  });
  bar.querySelector("[data-done]").addEventListener("click", function (e) {
    if (dirty.size) {
      e.preventDefault();
      state.textContent = "Save or undo your changes first";
      state.classList.add("dirty");
    }
  });
  refresh();
})();
