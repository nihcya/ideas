import 'package:dio/dio.dart';

import '../models/user.dart';
import 'api_client.dart';

/// 用户服务：获取用户公开主页（思维森林）
class UserService {
  final Dio _dio;

  UserService(this._dio);

  /// 获取用户公开主页
  Future<UserProfile> getUserProfile(String id) async {
    try {
      final res = await _dio.get('/users/$id');
      return UserProfile.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }
  /// 获取用户公开贡献记录（仅包含已发布公开创意中的正式署名）。
  Future<List<Map<String, dynamic>>> getUserContributions(
    String id, {
    int limit = 20,
    int offset = 0,
  }) async {
    try {
      final res = await _dio.get(
        '/users/$id/contributions',
        queryParameters: {'limit': limit, 'offset': offset},
      );
      final data = res.data as Map<String, dynamic>;
      return ((data['items'] as List<dynamic>?) ?? [])
          .map((item) => Map<String, dynamic>.from(item as Map))
          .toList();
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

}
