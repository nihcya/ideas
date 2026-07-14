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
}
