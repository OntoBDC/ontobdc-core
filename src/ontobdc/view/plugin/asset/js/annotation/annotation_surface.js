(function (global) {
  "use strict";

  async function imageSurface(file, context, options) {
    const url = URL.createObjectURL(file);
    const image = document.createElement("img");
    image.className = options.surfaceClass;
    image.alt = context.representationName || options.imageAlt;
    image.src = url;
    await new Promise(function (resolve, reject) {
      image.onload = resolve;
      image.onerror = function () {
        reject(new Error(options.imageLoadError));
      };
    });
    return {
      element: image,
      width: image.naturalWidth,
      height: image.naturalHeight,
      release: function () {
        URL.revokeObjectURL(url);
      },
    };
  }

  async function pdfSurface(file, options) {
    const pdfjs = await import(options.pdfModuleUrl);
    pdfjs.GlobalWorkerOptions.workerSrc = options.pdfWorkerUrl;
    const task = pdfjs.getDocument({
      data: new Uint8Array(await file.arrayBuffer()),
    });
    const pdf = await task.promise;
    const page = await pdf.getPage(options.pdfPageNumber);
    const viewport = page.getViewport({ scale: options.pdfScale });
    const canvas = document.createElement("canvas");
    canvas.className = options.surfaceClass;
    canvas.width = Math.ceil(viewport.width);
    canvas.height = Math.ceil(viewport.height);
    await page.render({
      canvasContext: canvas.getContext("2d"),
      viewport: viewport,
    }).promise;
    return {
      element: canvas,
      width: canvas.width,
      height: canvas.height,
      release: function () {
        pdf.destroy();
      },
    };
  }

  async function createSurface(context, configuration) {
    const options = Object.assign({
      surfaceClass: "ontobdc-annotation-image",
      imageAlt: "Annotatable representation",
      imageLoadError: "The image representation could not be loaded.",
      unsupportedError: "This format does not have an annotatable representation.",
      pdfModuleUrl: "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.min.mjs",
      pdfWorkerUrl: "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.worker.min.mjs",
      pdfPageNumber: 1,
      pdfScale: 2,
    }, configuration || {});
    const mediaType = context.mediaType || (context.file && context.file.type) || "";
    const representationSource = context.representationSource || "";
    if (
      mediaType.startsWith("image/")
      || /\.(png|jpe?g|webp|gif|bmp)$/i.test(representationSource)
    ) {
      return imageSurface(context.file, context, options);
    }
    if (
      mediaType === "application/pdf"
      || /\.pdf$/i.test(representationSource)
    ) {
      return pdfSurface(context.file, options);
    }
    throw new Error(options.unsupportedError);
  }

  global.OntoBDCAnnotationSurface = Object.freeze({
    createSurface: createSurface,
  });
}(globalThis));
