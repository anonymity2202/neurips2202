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


## Time and Space

All experiments were run on NVIDIA TITAN Xp 

1. butterflies

model     | #GPUs | train time |
---------|--------|-----|
train_butterflies_MMT     | 1 | ~5min    | 
train_butterflies_STRICT     | 1 | ~5min    | 
train_butterflies_EXPLAIN     | 1 | ~5min    | 

2. Chinese characters


model     | #GPUs | train time |
---------|--------|-----|
train_chineseChars_MMT     | 1 | ~3min    | 
train_chineseChars_STRICT     | 1 | ~3min    | 
train_chineseChars_EXPLAIN     | 1 | ~3min    | 

## References

[1] Singla, A., Bogunovic, I., Bartók, G., Karbasi, A. and Krause, A., Near-Optimally Teaching the Crowd to Classify, ICML, 2014.

[2] Mac Aodha, O., Su, S., Chen, Y., Perona, P. and Yue, Y., Teaching categories to human learners with visual explanations, CVPR, 2018.



