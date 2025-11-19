from exa_py import Exa

import os
from dotenv import load_dotenv

load_dotenv()
exa = Exa(api_key = os.getenv("EXA_API_KEY_1"))

result = exa.get_contents(
  ["tesla.com"],
  text = True
)

print(result)