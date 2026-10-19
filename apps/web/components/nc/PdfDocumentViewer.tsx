"use client";
// NC 図・写真タブの PDF 表示(react-pdf)。
// react-pdf(pdfjs-dist)はブラウザ専用の API(DOMMatrix 等)を読み込み時に使うため、
// ページ側で next/dynamic の ssr:false で読み込み、サーバー側の描画(SSR)では評価しない。
// (ページへ直接 import していた時は、サーバー側の描画が毎回 500 になっていた)
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

export default function PdfDocumentViewer(props: {
  file: string;
  pageNumber: number;
  width: number;
  className?: string;
  onLoadSuccess?: (doc: { numPages: number }) => void;
}) {
  return (
    <Document file={props.file} onLoadSuccess={props.onLoadSuccess} className={props.className}>
      <Page pageNumber={props.pageNumber} width={props.width} />
    </Document>
  );
}
