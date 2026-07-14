/// Web 平台 localStorage 实现
///
/// 在 Web 环境下使用 dart:html 的 window.localStorage
/// 替代 FlutterSecureStorage（后者依赖 SubtleCrypto，非 HTTPS 下不可用）
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
