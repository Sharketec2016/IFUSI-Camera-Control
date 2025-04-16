import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


df = pd.read_csv("../datatest.csv")


print(df.head(10))

plt.imshow(df)
plt.colorbar()
plt.show()

