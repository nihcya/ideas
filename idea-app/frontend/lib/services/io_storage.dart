/// 非 Web 平台的空实现（条件导入占位）
///
/// 实际存储逻辑由 StorageService 中的 FlutterSecureStorage 处理
/// 此文件仅在非 Web 平台编译时被导入，函数不会被调用
library;

void writeToLocalStorage(String key, String value) {
  throw UnsupportedError('localStorage is only available on Web');
}

String? readFromLocalStorage(String key) {
  throw UnsupportedError('localStorage is only available on Web');
}

void deleteFromLocalStorage(String key) {
  throw UnsupportedError('localStorage is only available on Web');
}
