"""统一异常体系。"""


class AppError(Exception):
    def __init__(self, code: int, message: str, data=None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)


class ParamError(AppError):
    def __init__(self, message: str = "参数错误"):
        super().__init__(400, message)


class AuthError(AppError):
    def __init__(self, message: str = "认证失败，请重新登录"):
        super().__init__(401, message)


class ForbiddenError(AppError):
    def __init__(self, message: str = "无权限执行该操作"):
        super().__init__(403, message)


class NotFoundError(AppError):
    def __init__(self, message: str = "资源不存在"):
        super().__init__(404, message)


class ConflictError(AppError):
    def __init__(self, message: str = "状态冲突", data=None):
        super().__init__(409, message, data)


class PayloadTooLargeError(AppError):
    def __init__(self, message: str = "文件过大"):
        super().__init__(413, message)


class UnsupportedMediaError(AppError):
    def __init__(self, message: str = "类型不支持"):
        super().__init__(415, message)


class RateLimitError(AppError):
    def __init__(self, message: str = "请求过于频繁，请稍后再试", retry_after: float = 1.0):
        super().__init__(429, message)
        self.retry_after = retry_after


class UnavailableError(AppError):
    def __init__(self, message: str = "依赖服务不可用"):
        super().__init__(503, message)


class UpstreamTimeoutError(AppError):
    def __init__(self, message: str = "上游服务超时"):
        super().__init__(504, message)
