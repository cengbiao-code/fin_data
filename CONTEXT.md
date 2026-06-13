# Context

## Glossary

- **港股 PDF 文本编码诊断**: Determine why text extracted from a Hong Kong financial-report PDF is unreadable or unusable for downstream classification. This term refers to diagnosing font resources, CMaps, ToUnicode availability, and extracted text quality. It is not visual font recognition or OCR.
- **候选解码文本**: Experimental text recovered during 港股 PDF 文本编码诊断. It may explain or debug an extraction failure, but it is not raw table evidence and must not be written to `raw_tables`, `raw_cells`, trusted facts, or other audit data stores until promoted through a separate extractor-adapter decision.
