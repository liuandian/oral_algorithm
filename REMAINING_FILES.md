# 剩余需要生成的文件清单

## 核心业务逻辑（4个）
1. app/core/evidence_pack.py - EvidencePack生成器
2. app/core/ingestion.py - 视频摄取模块  
3. app/core/llm_client.py - LLM报告生成
4. app/core/profile_manager.py - 用户档案管理

## 服务层（2个）
5. app/services/qianwen_vision.py - 千问API客户端
6. app/services/storage.py - 文件存储服务

## 工具函数（2个）
7. app/utils/hash.py - 文件Hash计算
8. app/utils/video.py - 视频处理工具

## 生成方式
由于这些文件之前已经编写过（但有编码问题），可以：
1. 从之前的代码中提取逻辑
2. 使用正确的UTF-8编码重新生成
3. 确保所有注释使用中文

## 当前状态
- ✓ 已完成：17个文件编译通过
- ⚠️ 待生成：8个文件
- 总进度：17/25 (68%)
