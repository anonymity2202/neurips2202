import argparse
import os
import shutil
import time

import torch
import torch.nn as nn
import torch.nn.parallel
import torch.backends.cudnn as cudnn
import torch.optim
import torch.utils.data
import numpy as np
import datasets2
import models as models
import matplotlib.pyplot as plt
import torchvision.models as torch_models
import scipy.io as sio
from PIL import Image


model_names = sorted(name for name in models.__dict__
                     if name.islower() and not name.startswith("__")
                     and callable(models.__dict__[name]))

parser = argparse.ArgumentParser(description='PyTorch butterflies')
parser.add_argument('-d', '--dataset', default='butterflies', help='dataset name')
parser.add_argument('--arch', '-a', metavar='ARCH', default='keras',
                    choices=model_names,
                    help='model architecture: ' +
                         ' | '.join(model_names) +
                         ' (default: resnet50)')
parser.add_argument('-c', '--channel', type=int, default=16,
                    help='first conv channel (default: 16)')
parser.add_argument('-j', '--workers', default=4, type=int, metavar='N',
                    help='number of data loading workers (default: 1)')
parser.add_argument('--gpu', default='1', help='index of gpus to use')
parser.add_argument('--iters', default=20, type=int, metavar='N',
                    help='number of total iters to run')
parser.add_argument('--start-epoch', default=0, type=int, metavar='N',
                    help='manual epoch number (useful on restarts)')
parser.add_argument('-b', '--batch-size', default=16, type=int,
                    metavar='N', help='mini-batch size (default: 200)')
parser.add_argument('--lr', '--learning-rate', default=0.001, type=float,
                    metavar='LR', help='initial learning rate')
parser.add_argument('--momentum', default=0.9, type=float, metavar='M',
                    help='momentum')
parser.add_argument('--weight-decay', '--wd', default=1e-4, type=float,
                    metavar='W', help='weight decay (default: 1e-4)')
parser.add_argument('--lr_step', default='2', help='decreasing strategy')
parser.add_argument('--print-freq', '-p', default=10, type=int,
                    metavar='N', help='print frequency (default: 10)')
parser.add_argument('--resume', default='', type=str, metavar='PATH',
                    help='path to latest checkpoint (default: none)')
parser.add_argument('-e', '--evaluate', dest='evaluate', action='store_true',
                    help='evaluate model on validation set')
parser.add_argument('--pretrained', dest='pretrained', action='store_true',
                    help='use pre-trained model')
parser.add_argument('--num_weaker', default=20, type=int, metavar='N',
                    help='number of first stage epochs to run')
parser.add_argument('--learning_rate', default=1, type=int, metavar='N',
                    help='number of first stage epochs to run')
parser.add_argument('--topK', default=10, type=int, metavar='N',
                    help='number of first stage epochs to run')
parser.add_argument('--S_max', default=1, type=int, metavar='N',
                    help='see professor writing')
parser.add_argument('--Lambda', default=10.0, type=int, metavar='N',
                    help='see professor writing')
parser.add_argument('--selection', default='random', help='see professor writing')


def main():
    global args, best_prec1
    args = parser.parse_args()

    # training multiple times

    # select gpus
    args.gpu = args.gpu.split(',')
    os.environ['CUDA_VISIBLE_DEVICES'] = ','.join(args.gpu)

    # data loader
    assert callable(datasets2.__dict__[args.dataset])
    get_dataset = getattr(datasets2, args.dataset)
    num_classes = datasets2._NUM_CLASSES[args.dataset]
    train_loader, val_loader = get_dataset(
        batch_size=args.batch_size, num_workers=args.workers)

    class Logistic(nn.Module):

        def __init__(self, num_classes=5):
            super(Logistic, self).__init__()
            self.conv1 = nn.Conv2d(3, 6, 5, 1)
            self.conv2 = nn.Conv2d(6, 16, 5, 1)

            self.bn1 = nn.BatchNorm2d(6)
            self.bn2 = nn.BatchNorm2d(16)

            self.maxpool1 = nn.MaxPool2d(2)
            self.maxpool2 = nn.MaxPool2d(2)

            self.relu = nn.ReLU(inplace=True)

            self.fc1 = nn.Linear(13456, 64)
            self.fc2 = nn.Linear(64, num_classes)


        def forward(self, x):
            x = self.conv1(x)
            x = self.bn1(x)
            x = self.relu(x)
            x = self.maxpool1(x)
            x = self.conv2(x)
            x = self.bn2(x)
            x = self.relu(x)
            x = self.maxpool2(x)
            x = x.view(x.size(0), -1)
            x = self.fc1(x)
            embedding = self.relu(x)
            x = self.fc2(embedding)

            return x, embedding

    # model_main = Logistic(num_classes=5)

    model_main = models.__dict__['resnet18_feature'](pretrained=True)
    if args.selection == 'MMT_largemargin':
        model_main.fc = nn.Linear(512 * 1, num_classes, bias=False)
    else:
        model_main.fc = nn.Linear(512 * 1, num_classes)
    model_main = torch.nn.DataParallel(model_main, device_ids=range(len(args.gpu))).cuda()

    criterion = nn.CrossEntropyLoss(reduce=False).cuda()
    criterion2 = nn.CrossEntropyLoss().cuda()
    cudnn.benchmark = True

    optimizer_m = torch.optim.SGD(model_main.parameters(), lr=0.0001, momentum=0.9, weight_decay=1e-4)
    # optimizer_m = torch.optim.Adam(model_main.parameters(), lr=0.001, weight_decay=1e-4)

    teaching_set = './datasets/butterflies_crop/' + args.selection + '/butterflies_Lt_gt_tr.txt'
    remaining_set = './datasets/butterflies_crop/' + args.selection + '/butterflies_Dt_gt_tr.txt'
    teaching_example_index = 0
    all_test_acc_iter = np.zeros(args.iters)
    all_train_acc_iter = np.zeros(args.iters)
    for iter in range(args.iters):

        if iter == 0:
            imlist = []
            labellist = []
            with open('./datasets/butterflies_crop/butterflies_gt_tr.txt', 'r') as rf:
                for line in rf.readlines():
                    impath, imlabel, imindex = line.strip().split()
                    imlist.append(impath)
                    labellist.append(imlabel)

            assert callable(datasets2.__dict__['butterflies'])
            get_dataset = getattr(datasets2, 'butterflies')
            num_classes = datasets2._NUM_CLASSES['butterflies']
            train_loader, val_loader = get_dataset(
                batch_size=1, num_workers=args.workers)

            if args.selection == 'MMT' or args.selection == 'MMT_largemargin':
                added_example_indices = selection(train_loader, model_main, optimizer_m, iter, criterion,
                                                  args.S_max, args.Lambda)
            elif args.selection == 'random':
                added_example_indices = selection_random(train_loader, model_main, optimizer_m, iter, criterion,
                                                         args.S_max, args.Lambda)

            added_example_indices = added_example_indices.tolist()
            fl = open(teaching_set, 'w')
            for k in range(len(added_example_indices)):
                example_info = imlist[added_example_indices[k]] + " " + labellist[added_example_indices[k]] + " " + str(teaching_example_index)
                fl.write(example_info)
                fl.write("\n")
                teaching_example_index = teaching_example_index + 1
            fl.close()

            # update Dt
            imlist = [i for j, i in enumerate(imlist) if j not in added_example_indices]
            labellist = [i for j, i in enumerate(labellist) if j not in added_example_indices]
            fl = open(remaining_set, 'w')
            num = 0
            for k in range(len(imlist)):
                example_info = imlist[k] + " " + labellist[k] + " " + str(num)
                fl.write(example_info)
                fl.write("\n")
                num = num + 1
            fl.close()

        else:
            assert callable(datasets2.__dict__['butterflies_Dt'])
            get_dataset = getattr(datasets2, 'butterflies_Dt')
            num_classes = datasets2._NUM_CLASSES['butterflies_Dt']
            train_loader_Dt, val_loader = get_dataset(
                batch_size=1, num_workers=args.workers, selection=args.selection)

            if args.selection == 'MMT' or args.selection == 'MMT_largemargin':
                added_example_indices = selection(train_loader_Dt, model_main, optimizer_m, iter, criterion,
                                                  args.S_max, args.Lambda)
            elif args.selection == 'random':
                added_example_indices = selection_random(train_loader_Dt, model_main, optimizer_m, iter, criterion,
                                                  args.S_max, args.Lambda)

            imlist = []
            labellist = []
            with open(remaining_set, 'r') as rf:
                for line in rf.readlines():
                    impath, imlabel, imindex = line.strip().split()
                    imlist.append(impath)
                    labellist.append(imlabel)


            fl = open(teaching_set, 'a')
            for k in range(len(added_example_indices)):
                example_info = imlist[added_example_indices[k]] + " " + labellist[added_example_indices[k]] + " " + str(
                    teaching_example_index)
                fl.write(example_info)
                fl.write("\n")
                teaching_example_index = teaching_example_index + 1
            fl.close()
            assert callable(datasets2.__dict__['butterflies_Lt'])
            get_dataset = getattr(datasets2, 'butterflies_Lt')
            num_classes = datasets2._NUM_CLASSES['butterflies_Lt']
            train_loader_Lt, val_loader = get_dataset(
                batch_size=teaching_example_index, num_workers=args.workers, selection=args.selection)

            if args.selection == 'MMT_largemargin' or args.selection == 'random':
                for epoch in range(10):
                    prec1_tr = train_largemargin(train_loader_Lt, model_main, optimizer_m, iter, criterion2)
            else:
                for epoch in range(1):
                    prec1_tr = train(train_loader_Lt, model_main, optimizer_m, iter, criterion2)

            print('training acc', prec1_tr.item())
            all_train_acc_iter[iter] = prec1_tr
            prec1 = validate(val_loader, model_main)
            print('testing acc', prec1.item())
            all_test_acc_iter[iter] = prec1

            # update Dt
            imlist = [i for j, i in enumerate(imlist) if j not in added_example_indices]
            labellist = [i for j, i in enumerate(labellist) if j not in added_example_indices]
            fl = open(remaining_set, 'w')
            num = 0
            for k in range(len(imlist)):
                example_info = imlist[k] + " " + labellist[k] + " " + str(num)
                fl.write(example_info)
                fl.write("\n")
                num = num + 1
            fl.close()

    np.save('./butterflies/all_train_acc_iter_' + args.selection + '.npy', all_train_acc_iter)
    np.save('./butterflies/all_test_acc_iter_' + args.selection + '.npy', all_test_acc_iter)
    # training evalution
    iteration = np.arange(0, args.iters)
    fig, ax = plt.subplots()
    ax.plot(iteration, all_train_acc_iter, '-b', label='train acc')
    ax.plot(iteration, all_test_acc_iter, '-r', label='test acc')
    leg = ax.legend()
    plt.xlabel('iteration')
    plt.ylabel('accuracy')
    plt.savefig('evolution_' + args.selection + '.jpg')


def selection(train_loader, model_main, optimizer_m, epoch, criterion, S_max, Lambda):

    # switch to train mode
    model_main.train()
    all_weights = []
    for i, (input, target, index) in enumerate(train_loader):

        input = input.cuda()
        # target = target.cuda(async=True)


        # compute output
        _, embeddings = model_main(input)  # embeddings is batch * 64

        # gradient is -e^-v
        codewords = model_main.module.fc.weight  # codewords is batch * 5 * 64

        embeddings = embeddings.detach().cpu().numpy()
        codewords = codewords.detach().cpu().numpy()

        y_c = codewords[target, :]
        y_c = np.tile(y_c, (5, 1))
        embeddings = np.tile(embeddings, (5, 1))
        embeddings = np.delete(embeddings, target, 0)
        y_c = np.delete(y_c, target, 0)
        codewords = np.delete(codewords, target, 0)
        weights = np.exp(-0.5 * np.sum(embeddings * (y_c - codewords), axis=1))
        weight = np.sum(weights)
        all_weights.append(weight)


    # select
    all_weights = np.array(all_weights)
    all_weights = torch.from_numpy(all_weights)

    sorted_weight, indices_weight = torch.sort(all_weights, descending=True)

    cum_weights = torch.cumsum(sorted_weight, dim=0)
    cost = Lambda * torch.exp(torch.range(1, S_max))
    L = cum_weights[:S_max] - cost
    _, S_star = L.max(0)
    # print(S_star.item())
    added_example_indices = indices_weight[:S_star+1]
    added_example_indices = added_example_indices.cpu().numpy()


    return added_example_indices


def selection_random(train_loader, model_main, optimizer_m, epoch, criterion, S_max, Lambda):

    # switch to train mode
    model_main.train()
    all_weights = []
    for i, (input, target, index) in enumerate(train_loader):
        input = input.cuda()
        # target = target.cuda(async=True)

        # compute output
        _, embeddings = model_main(input)  # embeddings is batch * 64

        # gradient is -e^-v
        codewords = model_main.module.fc.weight  # codewords is batch * 5 * 64

        embeddings = embeddings.detach().cpu().numpy()
        codewords = codewords.detach().cpu().numpy()

        y_c = codewords[target, :]
        y_c = np.tile(y_c, (5, 1))
        embeddings = np.tile(embeddings, (5, 1))
        embeddings = np.delete(embeddings, target, 0)
        y_c = np.delete(y_c, target, 0)
        codewords = np.delete(codewords, target, 0)
        weights = np.exp(-0.5 * np.sum(embeddings * (y_c - codewords), axis=1))
        weight = np.sum(weights)
        all_weights.append(weight)


    # select
    all_weights = np.array(all_weights)
    all_weights = torch.from_numpy(all_weights)

    sorted_weight, indices_weight = torch.sort(all_weights, descending=True)

    cum_weights = torch.cumsum(sorted_weight, dim=0)
    cost = Lambda * torch.exp(torch.range(1, S_max))
    L = cum_weights[:S_max] - cost
    _, S_star = L.max(0)

    indices_grad = torch.randperm(sorted_weight.shape[0])
    added_example_indices = indices_grad[:S_star+1]
    added_example_indices = added_example_indices.cpu().numpy()


    return added_example_indices




def train(train_loader, model_main, optimizer_m, epoch, criterion):

    losses_m = AverageMeter()
    top1 = AverageMeter()
    top5 = AverageMeter()

    # switch to train mode
    model_main.train()

    for i, (input, target, index) in enumerate(train_loader):


        input = input.cuda()
        target = target.cuda(async=True)

        # compute output
        predicted_labels, _ = model_main(input)

        loss_m = criterion(predicted_labels, target)
        prec1, prec5 = accuracy(predicted_labels, target, topk=(1, 5))
        losses_m.update(loss_m.item(), input.size(0))
        top1.update(prec1[0], input.size(0))
        top5.update(prec5[0], input.size(0))

        # compute gradient and do SGD step
        optimizer_m.zero_grad()
        loss_m.backward()
        optimizer_m.step()


    return top1.avg


def train_largemargin(train_loader, model_main, optimizer_m, epoch, criterion):

    losses_m = AverageMeter()
    top1 = AverageMeter()
    top5 = AverageMeter()

    # switch to train mode
    model_main.train()

    for i, (input, target, index) in enumerate(train_loader):


        input = input.cuda()
        target = target.cuda(async=True)

        # compute output
        predicted_labels, embeddings = model_main(input)

        z_c = predicted_labels[torch.arange(input.size(0)), target]
        z_c = torch.reshape(z_c, (input.size(0), 1))
        z_c = z_c.repeat(1, 5)
        loss = torch.exp(predicted_labels - z_c)
        loss_m = torch.mean(loss) - 1.0

        # loss_m = criterion(predicted_labels, target)

        prec1, prec5 = accuracy(predicted_labels, target, topk=(1, 5))
        losses_m.update(loss_m.item(), input.size(0))
        top1.update(prec1[0], input.size(0))
        top5.update(prec5[0], input.size(0))

        # compute gradient and do SGD step
        optimizer_m.zero_grad()
        loss_m.backward()
        optimizer_m.step()


    return top1.avg


def validate(val_loader, model_main):
    top1 = AverageMeter()
    # switch to evaluate mode
    model_main.eval()

    for i, (input, target, index) in enumerate(val_loader):

        input = input.cuda()
        target = target.cuda(async=True)

        # compute output
        output, _ = model_main(input)
        # measure accuracy and record loss
        prec1, prec5 = accuracy(output, target, topk=(1, 5))
        top1.update(prec1[0], input.size(0))

    return top1.avg


def save_predicted_hardness(train_loader, val_loader, model_ap):
    model_ap.eval()
    # hardness_scores_tr = []
    # hardness_scores_idx_tr = []
    # for i, (input, target, index) in enumerate(train_loader):
    #     input = input.cuda()
    #     predicted_hardness_scores = model_ap(input).squeeze()
    #     scores = predicted_hardness_scores.data.cpu().numpy()
    #     hardness_scores_tr = np.concatenate((hardness_scores_tr, scores), axis=0)
    #     index = index.numpy()
    #     hardness_scores_idx_tr = np.concatenate((hardness_scores_idx_tr, index), axis=0)

    hardness_scores_val = []
    hardness_scores_idx_val = []
    for i, (input, target, index) in enumerate(val_loader):
        input = input.cuda()
        predicted_hardness_scores = model_ap(input).squeeze()
        scores = predicted_hardness_scores.data.cpu().numpy()
        hardness_scores_val = np.concatenate((hardness_scores_val, scores), axis=0)
        index = index.numpy()
        hardness_scores_idx_val = np.concatenate((hardness_scores_idx_val, index), axis=0)

    return hardness_scores_val, hardness_scores_idx_val


def save_checkpoint(state, filename='checkpoint_res.pth.tar'):
    torch.save(state, filename)


class AverageMeter(object):
    """Computes and stores the average and current value"""

    def __init__(self):
        self.reset()

    def reset(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0

    def update(self, val, n=1):
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count

def adjust_learning_rate(optimizer, epoch):
    """Sets the learning rate to the initial LR decayed by 10 every 30 epochs"""
    lr = args.lr * (0.1 ** (epoch // 30))
    for param_group in optimizer.param_groups:
        param_group['lr'] = lr


def accuracy(output, target, topk=(1,)):
    """Computes the precision@k for the specified values of k"""
    maxk = max(topk)
    batch_size = target.size(0)

    _, pred = output.topk(maxk, 1, True, True)
    pred = pred.t()
    correct = pred.eq(target.view(1, -1).expand_as(pred))

    res = []
    for k in topk:
        correct_k = correct[:k].view(-1).float().sum(0, keepdim=True)
        res.append(correct_k.mul_(100.0 / batch_size))
    return res

if __name__ == '__main__':
    main()
