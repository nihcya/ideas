/// Web 平台 localStorage 实现
///
/// 在 Web 环境下使用 dart:html 的 window.localStorage
/// 替代 FlutterSecureStorage（后者依赖 SubtleCrypto，非 HTTPS 下不可用）
///
/// M5 安全说明：
/// - localStorage 不加密，任何 XSS 脚本可读取其中数据（含 JWT token）
/// - 当前 Flutter Web 用 Text 渲染，未发现 XSS 向量，可暂时使用
/// - HTTPS 部署后建议切回 FlutterSecureStorage（StorageService 已预留分支）
/// - 切勿在 localStorage 中存储额外敏感信息（如 API Key、密码）
/// - 引入任何第三方库或 HTML 渲染（HtmlElementView/Markdown）前必须重新评估
library;

import 'dart:html' show window;

void writeToLocalStorage(String key, String value) {
  window.localStorage[key] = value;
}

String? readFromLocalStorage(String key) {
  return window.localStorage[key];
}

void deleteFromLocalStorage(String key) {
  window.localStorage.remove(key);
}
