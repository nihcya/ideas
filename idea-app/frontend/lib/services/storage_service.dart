import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

// Web 环境下使用 dart:html 的 localStorage
// 条件导入：只在 Web 编译时引入 dart:html
// kIsWeb 守卫确保非 Web 平台不会执行 localStorage 代码
import 'web_storage.dart' if (dart.library.io) 'io_storage.dart'
    as platform_storage;

/// 跨平台安全存储服务
///
/// - Web 平台：使用 localStorage（SubtleCrypto 在非 HTTPS 下不可用，FlutterSecureStorage 会失败）
/// - 非 Web 平台：使用 FlutterSecureStorage（原生安全存储）
///
/// 注意：Web 平台下 localStorage 不加密，仅适用于非敏感数据。
/// 启用 HTTPS 后可切换回 FlutterSecureStorage。
class StorageService {
  final FlutterSecureStorage _secureStorage;

  StorageService([FlutterSecureStorage? storage])
      : _secureStorage = storage ?? const FlutterSecureStorage();

  /// 写入数据
  Future<void> write({required String key, required String value}) async {
    if (kIsWeb) {
      platform_storage.writeToLocalStorage(key, value);
    } else {
      await _secureStorage.write(key: key, value: value);
    }
  }

  /// 读取数据
  Future<String?> read({required String key}) async {
    if (kIsWeb) {
      return platform_storage.readFromLocalStorage(key);
    } else {
      return await _secureStorage.read(key: key);
    }
  }

  /// 删除数据
  Future<void> delete({required String key}) async {
    if (kIsWeb) {
      platform_storage.deleteFromLocalStorage(key);
    } else {
      await _secureStorage.delete(key: key);
    }
  }
}
