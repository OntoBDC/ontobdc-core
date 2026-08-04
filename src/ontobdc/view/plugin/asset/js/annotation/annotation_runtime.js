(function (global) {
  "use strict";

  function required(name) {
    if (!global[name]) throw new Error(name + " must be loaded before annotation_runtime.js.");
    return global[name];
  }
  const model = required("OntoBDCAnnotationModel");
  const stores = required("OntoBDCAnnotationStore");
  const surfaces = required("OntoBDCAnnotationSurface");
  const visualResolvers = required("OntoBDCAnnotationVisualResolver");
  const renderer = required("OntoBDCAnnotationRenderer");
  const editorFactory = required("OntoBDCAnnotationEditor");
  const geometryFactory = required("OntoBDCAnnotationGeometryController");
  const lifecycle = required("OntoBDCAnnotationLifecycle");
  const workspaceFactory = required("OntoBDCAnnotationWorkspace");
  const subjectPageFactory = required("OntoBDCSubjectPage");

  function createRuntime(configuration) {
    const options = Object.assign({ prefix: "ontobdc", bodyOpenClass: "has-annotation-dialog", normalizeContext: function (v) { return v; }, store: {}, surface: {}, visual: {}, labels: {} }, configuration || {});
    options.labels = Object.assign({
      annotation: "Annotation", emptyAnnotation: "Annotation without text.", showAnnotation: "Show annotation: ", closeAnnotation: "Close annotation",
      previewUnavailable: "The preview area is not available.", openCancelled: "Opening the annotation was cancelled.",
      application: "OntoBDC Annotation", resource: "Resource", dialog: "Annotate representation", close: "Close",
      category: "Category", newAnnotation: "New annotation", delete: "Delete", save: "Save",
      categoryLabels: { NoteAnnotation: "Note", IssueAnnotation: "Issue", ClassificationAnnotation: "Classification", LocationAnnotation: "Location", RecordAnnotation: "Record" },
      toolLabels: { select: "Select", point: "Point", "multiple-points": "Multiple points", "bounding-box": "Bounding box", clear: "Clear geometry" },
      fieldLabels: {}, valueLabels: {}, invalidGeometry: "The selected geometry is not valid for this annotation category.", saveError: "The annotation could not be saved.",
    }, options.labels || {});
    const store = stores.createFileSystemStore(options.store);
    const visualResolver = visualResolvers.createResolver(options.visual);
    const previewSurfaces = new WeakMap();
    let dialog = null; let dialogRelease = null; let dialogOnClose = null; let openGeneration = 0;

    function normalizeContext(raw) {
      const value = options.normalizeContext(raw || {});
      if (!value || !value.containerHandle) throw new Error("An annotation context with a container handle is required.");
      return value;
    }
    function ensureOpenIsActive(generation, surface) {
      if (generation === openGeneration) return;
      if (surface && surface.release) surface.release();
      throw new DOMException(options.labels.openCancelled, "AbortError");
    }
    function cancelOpen() { openGeneration += 1; }
    function close() {
      const onClose = dialogOnClose; dialogOnClose = null;
      if (dialogRelease) { dialogRelease(); dialogRelease = null; }
      if (dialog) { dialog.remove(); dialog = null; }
      document.body.classList.remove(options.bodyOpenClass);
      if (onClose) Promise.resolve(onClose()).catch(console.error);
    }
    function clearPreview(raw) {
      const context = raw && options.normalizeContext(raw); const preview = context && context.previewElement;
      if (!preview) return;
      const release = previewSurfaces.get(preview); if (release) { release(); previewSurfaces.delete(preview); }
    }
    function matchesContext(annotation, context) { return model.matchesContext(annotation, context); }

    async function showPreview(raw) {
      const context = normalizeContext(raw); const preview = context.previewElement;
      if (!preview) throw new Error(options.labels.previewUnavailable);
      clearPreview(raw); await store.load(context.containerHandle);
      const surface = await surfaces.createSurface(context, Object.assign({ surfaceClass: options.prefix + "-annotation-image" }, options.surface));
      const result = renderer.renderPreview(context, store.list(), surface, {
        prefix: options.prefix, annotationLabel: options.labels.annotation, emptyAnnotationLabel: options.labels.emptyAnnotation,
        showAnnotationLabel: options.labels.showAnnotation, closeLabel: options.labels.closeAnnotation,
        categoryLabels: options.labels.categoryLabels, matchesContext: matchesContext, visualResolver: visualResolver,
      });
      preview.replaceChildren(result.element); previewSurfaces.set(preview, surface.release); return result.count;
    }

    function validateGeometry(category, selector, hasRepresentation, properties) {
      const type = selector && model.localName(selector.type);
      if (category === "NoteAnnotation" && hasRepresentation && type !== "PointSelector") return false;
      if (category === "ClassificationAnnotation" && hasRepresentation && type !== "BoundingBoxSelector") return false;
      if (category === "LocationAnnotation") {
        const locationKind = model.localName(properties.locationKind);
        if (locationKind === "RepresentationLocation" && type !== "PointSelector") return false;
        if (locationKind === "GeospatialLocation" && (properties.latitude == null || properties.longitude == null)) return false;
        if (locationKind === "RelativeLocation" && (!properties.relativeTo || !properties.spatialRelation)) return false;
      }
      if (category === "LocationAnnotation" && selector && !["PointSelector", "BoundingBoxSelector"].includes(type)) return false;
      if (category === "RecordAnnotation" && selector && !["PointSelector", "BoundingBoxSelector"].includes(type)) return false;
      if (category === "IssueAnnotation" && selector && !["PointSelector", "BoundingBoxSelector"].includes(type)) return false;
      return true;
    }

    async function open(raw) {
      const context = normalizeContext(raw); const generation = ++openGeneration;
      await store.load(context.containerHandle); ensureOpenIsActive(generation);
      const surface = await surfaces.createSurface(context, Object.assign({ surfaceClass: options.prefix + "-annotation-image" }, options.surface));
      ensureOpenIsActive(generation, surface);
      const representationHash = await model.digest(context.file); ensureOpenIsActive(generation, surface); close();
      const editor = editorFactory.createEditor(context, surface, {
        prefix: options.prefix, applicationLabel: options.labels.application, resourceLabel: options.labels.resource,
        dialogLabel: options.labels.dialog, categoryLabel: options.labels.category, closeLabel: options.labels.close,
        newLabel: options.labels.newAnnotation, deleteLabel: options.labels.delete, saveLabel: options.labels.save,
        categoryLabels: options.labels.categoryLabels, toolLabels: options.labels.toolLabels,
        fieldLabels: options.labels.fieldLabels, valueLabels: options.labels.valueLabels,
      });
      document.body.appendChild(editor.root); document.body.classList.add(options.bodyOpenClass);
      dialog = editor.root; dialogRelease = surface.release; dialogOnClose = typeof context.onClose === "function" ? context.onClose : null;
      const session = { context: context, width: surface.width, height: surface.height, overlay: editor.annotationOverlay, selectedId: null, points: [], color: { value: options.store.defaultColor || "#67e8f9" } };
      const geometry = geometryFactory.createController(editor.stage, editor.geometryOverlay, { sourceWidth: surface.width, sourceHeight: surface.height });

      function renderAnnotations() {
        renderer.renderEditorMarkers(session, store.list(), {
          prefix: options.prefix, categoryLabels: options.labels.categoryLabels, matchesContext: matchesContext,
          visualResolver: visualResolver, showAnnotationLabel: options.labels.showAnnotation, emptyAnnotationLabel: options.labels.emptyAnnotation,
          onSelect: selectAnnotation,
        });
      }
      function reset() {
        session.selectedId = null; editor.lockCategory(false); editor.setCategory("NoteAnnotation"); editor.deleteButton.disabled = true; editor.showError(""); geometry.clear(); renderAnnotations();
      }
      function selectAnnotation(annotation) {
        session.selectedId = annotation.id; const category = model.localName(annotation.type);
        const form = editor.setCategory(category); form.load(annotation); editor.lockCategory(true); editor.deleteButton.disabled = false;
        geometry.setSelector(annotation.selector); renderAnnotations();
      }
      editor.root.addEventListener("ontobdc:categorychange", function () { geometry.clear(); editor.showError(""); });
      editor.toolbar.addEventListener("click", function (event) {
        const button = event.target.closest("[data-geometry-tool]"); if (!button) return;
        const tool = button.dataset.geometryTool;
        if (tool === "clear") geometry.clear(); else geometry.setMode(tool);
        editor.toolbar.querySelectorAll("[data-geometry-tool]").forEach(function (item) { item.setAttribute("aria-pressed", String(item === button)); });
      });
      editor.closeButton.addEventListener("click", close); editor.newButton.addEventListener("click", reset);
      editor.saveButton.addEventListener("click", async function () {
        editor.showError("");
        try {
          const category = editor.category.value; const values = editor.getForm().read(); const selector = geometry.getSelector();
          if (!validateGeometry(category, selector, Boolean(context.representationSource), values.properties)) throw new TypeError(options.labels.invalidGeometry);
          const existing = store.list().find(function (item) { return item.id === session.selectedId; });
          let annotation = model.createAnnotation(model.TYPES[category], {
            id: existing && existing.id, created: existing && existing.created, body: values.body,
            logicalSource: context.logicalSource, representationSource: context.representationSource || null,
            representationHash: context.representationSource ? representationHash : null,
            relatedDimension: context.dimension || null, selector: selector, properties: values.properties,
            subjects: values.subjects || (existing && existing.subjects) || [],
            assignedTo: values.assignedTo || (existing && existing.assignedTo) || [],
            resolvedBy: values.resolvedBy || (existing && existing.resolvedBy) || null,
            annotatedBy: existing && existing.annotatedBy,
            annotatedAt: existing && existing.annotatedAt,
            modified: existing && existing.modified,
            modifiedBy: existing && existing.modifiedBy,
          });
          annotation = model.normalizeAnnotation(lifecycle.apply(annotation, context, existing));
          store.upsert(annotation); await store.persist(context.containerHandle); selectAnnotation(annotation);
        } catch (error) { editor.showError((error && error.message) || options.labels.saveError); }
      });
      editor.deleteButton.addEventListener("click", async function () {
        if (!session.selectedId) return; store.remove(session.selectedId); await store.persist(context.containerHandle); reset();
      });
      renderAnnotations();
    }

    async function openWorkspace(element, raw, configuration) {
      const context = normalizeContext(raw);
      await store.load(context.containerHandle);
      const workspace = workspaceFactory.create(Object.assign({
        annotations: store.list(),
        visualResolver: visualResolver,
        onOpen: function (annotation) {
          if (context.openAnnotation) context.openAnnotation(annotation);
        },
      }, configuration || {}));
      element.replaceChildren(workspace.root);
      return workspace;
    }
    async function openSubjectPage(element, raw, subjectUri, configuration) {
      const context = normalizeContext(raw);
      await store.load(context.containerHandle);
      const page = subjectPageFactory.create(Object.assign({
        annotations: store.list(),
        subjectUri: subjectUri || null,
        onOpen: function (annotation) {
          if (context.openAnnotation) context.openAnnotation(annotation);
        },
      }, configuration || {}));
      element.replaceChildren(page.root);
      return page;
    }
    document.addEventListener("keydown", function (event) { if (event.key === "Escape" && dialog) close(); });
    return Object.freeze({
      cancelOpen, clearPreview, close, decoratePreview: showPreview, open, showPreview,
      openWorkspace, openSubjectPage, listAnnotations: store.list,
    });
  }

  global.OntoBDCAnnotations = Object.freeze({ createRuntime: createRuntime });
}(globalThis));
