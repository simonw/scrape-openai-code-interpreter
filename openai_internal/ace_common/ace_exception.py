class AceException(Exception):
    pass


class UserMachineResponseTooLarge(AceException):
    pass


class AceConnectionException(AceException):
    pass


class AceInternalException(AceException):
    pass


class AceTimeoutException(AceConnectionException):
    pass


class AceTooManyRequestsException(AceException):
    pass


class AceResourceNotFoundException(AceException):
    pass


class AceFileNotFoundException(AceResourceNotFoundException):
    pass


                           
class CodeExecutorTimeoutError(AceException):
    pass


                                                   
class TimeoutInterruptError(AceException):
    pass


                                                 
class AsyncioCancelledError(AceException):
    pass


                                                                                                              
class UnexpectedSystemError(AceException):
    pass
