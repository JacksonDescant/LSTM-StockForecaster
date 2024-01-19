# -*- coding: utf-8 -*-
"""LSTMStockForecaster.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1bNN64IQ7j2Kw8g0hFSGjzuAs9QpJVy_z
"""

import yfinance as yf
import pandas as pd
import torch
import torch.nn as nn
from copy import deepcopy as dc
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from torch.utils.data import Dataset
from torch.utils.data import DataLoader
import matplotlib.pyplot as plt

print('Loading Market Data...')
SPY = yf.download('SPY', start='2000-01-01', end=None)
print('Done!')
SPY.to_csv('spyData.csv')

spyDF = pd.read_csv('spyData.csv')
spyDF = spyDF[['Date', 'Close']]

device = 'cuda:0' if torch.cuda.is_available() else 'cpu'


def spyDF_lstm_prep(spyDF, nSteps):
    spyDF = dc(spyDF)
    spyDF['Date'] = pd.to_datetime(spyDF['Date'])
    spyDF.set_index('Date', inplace=True)

    for i in range(1, nSteps + 1):
        spyDF[f'Close(t-{i})'] = spyDF['Close'].shift(i)

    spyDF.dropna(inplace=True)

    return spyDF


closeHistory = 10
shiftedCloseDF = spyDF_lstm_prep(spyDF, closeHistory)


shiftedCloseDFtoNP = shiftedCloseDF.to_numpy()


scaler = MinMaxScaler(feature_range=(-1, 1))
shiftedCloseDFtoNP = scaler.fit_transform(shiftedCloseDFtoNP)

x = shiftedCloseDFtoNP[:, 1:]
y = shiftedCloseDFtoNP[:, 0]


x = dc(np.flip(x, axis=1))

splitIndex = int(len(x) * 0.9)

xTrain = x[:splitIndex]
xTest = x[splitIndex:]

yTrain = y[:splitIndex]
yTest = y[splitIndex:]

xTrain = xTrain.reshape((-1, closeHistory, 1))
xTest = xTest.reshape((-1, closeHistory, 1))

yTrain = yTrain.reshape((-1, 1))
yTest = yTest.reshape((-1, 1))


xTrain = torch.tensor(xTrain).float()
xTest = torch.tensor(xTest).float()
yTrain = torch.tensor(yTrain).float()
yTest = torch.tensor(yTest).float()

class TimeSeriesDataset(Dataset):
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __len__(self):
        return len(self.x)

    def __getitem__(self, i):
        return self.x[i], self.y[i]


trainDataset = TimeSeriesDataset(xTrain, yTrain)
testDataset = TimeSeriesDataset(xTest, yTest)


batch = 16
trainLoader = DataLoader(trainDataset, batch, shuffle=True)
testLoader = DataLoader(testDataset, batch, shuffle=False)

for _, batch in enumerate(trainLoader):
    xBatch = batch[0].to(device)
    yBatch = batch[1].to(device)
    print(xBatch.shape, yBatch.shape)
    break


class LSTM(nn.Module):
    def __init__(self, inputSize, hiddenSize, numStack):
        super().__init__()
        self.hiddenSize = hiddenSize
        self.numStack = numStack
        self.lstm = nn.LSTM(inputSize, hiddenSize, numStack, batch_first=True)
        self.fc = nn.Linear(hiddenSize, 1)

    def forward(self, x):
        batch = x.size(0)
        h0 = torch.zeros(self.numStack, batch, self.hiddenSize).to(device)
        c0 = torch.zeros(self.numStack, batch, self.hiddenSize).to(device)
        out, _ = self.lstm(x, (h0, c0))
        out = self.fc(out[:, -1, :])
        return out


model = LSTM(1, 4, 1)
model.to(device)


def train_one_epoch():
    model.train(True)
    print(f'Epoch: {epoch + 1}')
    runningLoss = 0.0

    for batchIndex, batch in enumerate(trainLoader):
        xBatch, yBatch = batch[0].to(device), batch[1].to(device)

        output = model(xBatch)
        loss = lossFunction(output, yBatch)
        runningLoss = runningLoss + loss.item()
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        if batchIndex % 100 == 99:
            averageBatchLoss = runningLoss / 100
            print('Batch {0}, Loss: {1:.3f}'.format(batchIndex + 1, averageBatchLoss))
            runningLoss = 0.0


print()


def validate_one_epoch():
    model.train(False)
    runningLoss = 0.0

    for batchIndex, batch in enumerate(testLoader):
        xBatch, yBatch = batch[0].to(device), batch[1].to(device)

        with torch.no_grad():
            output = model(xBatch)
            loss = lossFunction(output, yBatch)
            runningLoss = runningLoss + loss.item()

    averageBatchLoss = runningLoss / len(testLoader)

    print('Value loss: {0:.3f}'.format(averageBatchLoss))
    print('-------------------------------------------')
    print()


learningRate = 0.001
epochNum = 10
lossFunction = nn.MSELoss()
optimizer = torch.optim.Adam(model.parameters(), lr=learningRate)

for epoch in range(epochNum):
    train_one_epoch()
    validate_one_epoch()


with torch.no_grad():
    predicted = model(xTrain.to(device)).to('cpu').numpy()

plt.plot(yTrain, label='Actual Close')
plt.plot(predicted, label='Predicted Close')
plt.xlabel('Day')
plt.ylabel('Close')
plt.legend()
plt.show()

trainPredictions = predicted.flatten()

revert = np.zeros((xTrain.shape[0], closeHistory + 1))
revert[:, 0] = trainPredictions
revert = scaler.inverse_transform(revert)

trainPredictions = dc(revert[:, 0])

revert = np.zeros((xTrain.shape[0], closeHistory + 1))
revert[:, 0] = yTrain.flatten()
revert = scaler.inverse_transform(revert)

newYTrain = dc(revert[:, 0])

plt.plot(newYTrain, label='Actual Close')
plt.plot(trainPredictions, label='Predicted Close')
plt.xlabel('Day')
plt.ylabel('Close')
plt.legend()
plt.show()

testPredictions = model(xTest.to(device)).detach().cpu().numpy().flatten()
revert = np.zeros((xTest.shape[0], closeHistory + 1))
revert[:, 0] = testPredictions
revert = scaler.inverse_transform(revert)
testPredictions = dc(revert[:, 0])

revert = np.zeros((xTest.shape[0], closeHistory + 1))
revert[:, 0] = yTest.flatten()
revert = scaler.inverse_transform(revert)

newYTest = dc(revert[:, 0])

plt.plot(newYTest, label='Actual Close')
plt.plot(testPredictions, label='Predicted Close')
plt.xlabel('Day')
plt.ylabel('Close')
plt.legend()
plt.show()

torch.save(model.state_dict(), 'model_weights.pth')