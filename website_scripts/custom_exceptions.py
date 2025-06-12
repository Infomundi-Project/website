class InfomundiCustomException(Exception):
    def __init__(self, message="An unknown error has happened."):
        self.message = message
        super().__init__(self.message)