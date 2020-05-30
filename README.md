# neurips2202

## Requirements

1. The project was implemented and tested in Python 3.5 and Pytorch 1.0. Other versions should work after minor modification.
2. Other common modules like numpy, pandas and seaborn for visualization.
3. NVIDIA GPU and cuDNN are required to have fast speeds. For now, CUDA 8.0 with cuDNN 6.0.20 has been tested. The other versions should be working.


## Datasets

[Butterflies and Chinese Characters](https://github.com/macaodha/explain_teach/tree/master/data) are used. Please organize them as below after download,


```
datasets
|_ butterflies_crop
  |_ images
    |_ Viceroy
    |_ ...
```

```
datasets
|_ chinese_chars
  |_ images
    |_ grass
    |_ ...
```

## Implementation details

### To reproduce our method
on simulated learners
```
train_butterflies_MMT.py
train_chineseChars_MMT.py
```
on real learners
```
train_butterflies_MMT_real.py
train_chineseChars_MMT_real.py
```

### To reproduce STRICT
```
train_butterflies_STRICT.py
train_chineseChars_STRICT.py
```

### To reproduce EXPLAIN
```
train_butterflies_EXPLAIN.py
train_chineseChars_EXPLAIN.py
```




