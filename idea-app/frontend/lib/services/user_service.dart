import 'package:dio/dio.dart';

import '../models/user.dart';
import 'api_client.dart';

/// 用户服务：获取用户公开主页（思维森林）
class UserService {
  final Dio _dio;

  UserService(this._dio);

  /// 搜索公开创作者；排序和贡献统计仅基于当前公开内容。
  Future<List<Map<String, dynamic>>> searchPublicCreators(
    String query, {
    int limit = 20,
    int offset = 0,
  }) async {
    try {
      final res = await _dio.get('/users/search', queryParameters: {
        'q': query,
        'limit': limit,
        'offset': offset,
      });
      final data = Map<String, dynamic>.from(res.data as Map);
      return ((data['items'] as List<dynamic>?) ?? [])
          .map((item) => Map<String, dynamic>.from(item as Map))
          .toList();
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  /// 获取用户公开主页
  Future<UserProfile> getUserProfile(String id) async {
    try {
      final res = await _dio.get('/users/$id');
      return UserProfile.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }
  /// 获取用户公开贡献记录分页（仅包含已发布公开创意中的正式署名）。
  Future<Map<String, dynamic>> getUserContributionsPage(
    String id, {
    int limit = 20,
    int offset = 0,
  }) async {
    try {
      final res = await _dio.get(
        '/users/$id/contributions',
        queryParameters: {'limit': limit, 'offset': offset},
      );
      final data = Map<String, dynamic>.from(res.data as Map);
      data['items'] = ((data['items'] as List<dynamic>?) ?? [])
          .map((item) => Map<String, dynamic>.from(item as Map))
          .toList();
      return data;
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  /// 兼容旧调用方的列表形式。
  Future<List<Map<String, dynamic>>> getUserContributions(
    String id, {
    int limit = 20,
    int offset = 0,
  }) async {
    final page = await getUserContributionsPage(
      id, limit: limit, offset: offset,
    );
    return List<Map<String, dynamic>>.from(page['items'] as List);
  }

}
