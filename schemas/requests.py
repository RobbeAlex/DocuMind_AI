from pydantic import BaseModel

class PeticionConsulta(BaseModel):
    pregunta: str
