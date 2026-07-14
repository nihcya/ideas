import 'package:dio/dio.dart';

import '../models/vault.dart';
import 'api_client.dart';

/// 仓库服务：获取仓库 / 收集 / 移出
class VaultService {
  final Dio _dio;

  VaultService(this._dio);

  /// 获取当前用户的仓库圆圈列表
  Future<VaultResponse> getVault({
    int limit = 50,
    int offset = 0,
  }) async {
    try {
      final res = await _dio.get('/vault', queryParameters: {
        'limit': limit,
        'offset': offset,
      });
      return VaultResponse.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  /// 收集一个别人的点子到仓库
  Future<CollectResponse> collectIdea(String ideaId) async {
    try {
      final res = await _dio.post('/vault/$ideaId/collect', data: {});
      return CollectResponse.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  /// 将点子从仓库移出
  Future<RemoveResponse> removeFromVault(String ideaId) async {
    try {
      final res = await _dio.delete('/vault/$ideaId');
      return RemoveResponse.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }
}
