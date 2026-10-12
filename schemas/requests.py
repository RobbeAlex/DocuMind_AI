from pydantic import BaseModel
from typing import Optional

class PeticionConsulta(BaseModel):
    pregunta: str
    documento: Optional[str] = None
