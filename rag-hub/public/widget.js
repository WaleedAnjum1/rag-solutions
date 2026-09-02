/**
 * RAG Hub — Embeddable Widget
 *
 * Usage (add to any page):
 *   <script
 *     src="http://localhost:3000/widget.js"
 *     data-service="medical"
 *     data-patient-id="PT-001"
 *     data-accent="#00d4aa"
 *     data-position="bottom-right"
 *     data-base-url="http://localhost:3000">
 *   </script>
 */
(function () {
  var script = document.currentScript || (function () {
    var scripts = document.getElementsByTagName("script");
    return scripts[scripts.length - 1];
  })();

  var baseUrl = script.getAttribute("data-base-url") || "http://localhost:3000";
  var service = script.getAttribute("data-service") || "docs";
  var patientId = script.getAttribute("data-patient-id") || "";
  var accent = script.getAttribute("data-accent") || (service === "medical" ? "#00d4aa" : "#818cf8");
  var position = script.getAttribute("data-position") || "bottom-right";

  // Position styles
  var posStyles = {
    "bottom-right": { bottom: "24px", right: "24px" },
    "bottom-left":  { bottom: "24px", left: "24px"  },
    "top-right":    { top: "24px",    right: "24px"  },
    "top-left":     { top: "24px",    left: "24px"   },
  };
  var pos = posStyles[position] || posStyles["bottom-right"];

  // Build iframe URL
  var params = new URLSearchParams({ service: service, accent: accent });
  if (patientId) params.set("patientId", patientId);
  var iframeSrc = baseUrl + "/widget?" + params.toString();

  // State
  var open = false;
  var iframe, panel;

  // Floating button
  var btn = document.createElement("button");
  btn.id = "rag-hub-widget-btn";
  Object.assign(btn.style, {
    position: "fixed",
    zIndex: "999999",
    width: "56px",
    height: "56px",
    borderRadius: "50%",
    background: accent,
    border: "none",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    boxShadow: "0 4px 24px " + accent + "55",
    transition: "transform 200ms ease, box-shadow 200ms ease",
    fontSize: "22px",
    lineHeight: "1",
  });
  Object.assign(btn.style, pos);
  btn.innerHTML = "💬";
  btn.title = "Open RAG Assistant";

  btn.addEventListener("mouseenter", function () {
    btn.style.transform = "scale(1.1)";
    btn.style.boxShadow = "0 6px 32px " + accent + "77";
  });
  btn.addEventListener("mouseleave", function () {
    btn.style.transform = "scale(1)";
    btn.style.boxShadow = "0 4px 24px " + accent + "55";
  });

  btn.addEventListener("click", function () {
    open ? closePanel() : openPanel();
  });

  // Panel container
  panel = document.createElement("div");
  panel.id = "rag-hub-widget-panel";
  Object.assign(panel.style, {
    position: "fixed",
    zIndex: "999998",
    width: "min(420px, calc(100vw - 32px))",
    height: "min(600px, calc(100dvh - 120px))",
    borderRadius: "16px",
    overflow: "hidden",
    boxShadow: "0 24px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.08)",
    display: "none",
    transform: "scale(0.95) translateY(12px)",
    opacity: "0",
    transition: "transform 200ms ease, opacity 200ms ease",
  });

  // Position panel above the button
  if (pos.right)  panel.style.right  = pos.right;
  if (pos.left)   panel.style.left   = pos.left;
  if (pos.bottom) panel.style.bottom = (parseInt(pos.bottom) + 72) + "px";
  if (pos.top)    panel.style.top    = (parseInt(pos.top) + 72) + "px";

  // iframe (lazy-loaded on first open)
  function openPanel() {
    open = true;
    btn.innerHTML = "✕";

    if (!iframe) {
      iframe = document.createElement("iframe");
      iframe.src = iframeSrc;
      iframe.style.width = "100%";
      iframe.style.height = "100%";
      iframe.style.border = "none";
      iframe.allow = "clipboard-write";
      panel.appendChild(iframe);
    }

    panel.style.display = "block";
    // Animate in
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        panel.style.transform = "scale(1) translateY(0)";
        panel.style.opacity = "1";
      });
    });
  }

  function closePanel() {
    open = false;
    btn.innerHTML = "💬";
    panel.style.transform = "scale(0.95) translateY(12px)";
    panel.style.opacity = "0";
    setTimeout(function () {
      if (!open) panel.style.display = "none";
    }, 200);
  }

  document.body.appendChild(btn);
  document.body.appendChild(panel);
})();
