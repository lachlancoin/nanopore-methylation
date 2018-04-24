# ! /usr/bin/env python
"""
__author__ = Yao LI
__email__ = yao.li.binf@gmail.com
__date__ = 08/02/2018
"""


#############################
#  Human Imprinted Regions  #
#############################
class ImprintedRegion:
    def __init__(self, name, chr, start, end, status=""):
        self.gene = name
        self.chr = "chr"+chr
        self.start = int(start)  # hg38
        self.end = int(end)
        self.status = status

        self.reads = []  # reads have overlapped with this imprinted region

    def __str__(self):
        return "Gene:{}, chr:{}, {}:{}".format(self.gene, self.chr, self.start, self.end)


def read_imprinted_data(fn):
    """
    Obtain human imprinted regions information.
    :param fn: string, file name
    :return: a list of ImprintedRegion objects
    """
    regions = []
    f = open(fn, "r")
    for line in f:
        line = line.strip().split("\t")
        IR = ImprintedRegion(line[0], line[3], line[1], line[2])
        regions.append(IR)
    f.close()
    return regions


############################
# Nanopore sequencing data #
############################
class NanoporeRead:
    """
    A nanopore sequencing snp instance. NA12878 data.
    """

    def __init__(self, sequencer_id, chrom, fastq_seq, start, end, rs=None):
        # Basic attr
        self.id = sequencer_id
        self.chr = chrom
        self.raw_signal = rs  # TODO: use
        self.seq = fastq_seq
        self.start = int(start)
        self.end = int(end)
        self.length = len(self.seq)

        # SNP attr
        self.snps = []
        self.snps_id = []
        self.bases = []  # NO NEED
        self.gt = ""

        # Imprinted regions attr
        self.if_ir = False
        self.region = None
        self.gene_name = ""
        self.segment_pos = [0, self.length]  # overlap segment, snp_id on snp
        self.seg_ref_pos = [0, 0]  # segment pos on ref genome

        # Markov model attr
        self.model1_probs = []
        self.model2_probs = []
        self.model = None  # HMM model

    def if_in_imprinted_region(self, ip_regions):
        """Decide if the snp has at least one base overlapping with any imprinted region."""
        for region in ip_regions:
            if self.chr == region.chr:
                if region.start <= self.start <= region.end or region.start <= self.end <= region.end:
                    self.region = region
                    self.gene_name = region.gene
                    self.seg_ref_pos = [self.start, self.end]
                    self.if_ir = True
        return self.if_ir

    def detect_snps(self, SNPs_data):
        """
        Find snps in one READs.
        :param SNPs_data: (list) class SNPs objects
        """
        for snp_id, snp in enumerate(SNPs_data):  # each SNPs instance, attr: chr, id, pos, ref, alt, gt
            if snp.chrom == self.chr and self.start <= snp.pos <= self.end:  # if position
                self.snps.append(snp)
                self.snps_id.append(snp_id)

    def detect_genotype(self):
        """Based on SNPs located in the read, count the majority genotype."""
        A = 0; B = 0
        for snp in self.snps:
            base = self.get_base(snp.pos)
            if snp.gt == "1|0":
                if base == snp.alt:
                    A += 1
                else:
                    B += 1
            elif snp.gt == "0|1":
                if base == snp.alt:
                    B += 1
                else:
                    A += 1
        if A > B:
            self.gt = "1|0"
        elif A < B:
            self.gt = "0|1"
        else:
            self.gt = "1|1"

    def get_raw_signals(self):
        """Extract raw signals for the snp"""
        pass

    def get_bases(self):  # NO NEED
        """
        Get bases on SNP positions on READs sequence.
        :return: list of string, bases, ATCG
        """
        for snp in self.snps:
            index = int(snp.pos) - int(self.start)
            self.bases.append(self.seq[index])
        return self.bases

    def get_base(self, pos):
        """
        Extract sequence bases on given position.
        :param pos: ref genome position
        :return: (str) a bases on sequence
        """
        try:
            index = int(pos) - int(self.start)
            return self.seq[index]
        except IndexError:
            #pass
            raise IndexError("snp pos not right.")

    def set_raw_signal(self, rs):
        """
        Set the raw signal for snp.
        :param rs: (numpy array) raw signal
        """
        self.raw_signal = rs

    def set_model(self, model):
        """HMM model status, int, m1 or m2."""
        self.model = model

    def __str__(self):
        return "{}:\t{}:{},{}".format(self.id, self.chr, self.start, self.end)

    def __eq__(self, other):
        """Override the default Equals behavior"""
        return self.id == other.id and self.model == other.state

    def __ne__(self, other):
        """Override the default Unequal behavior"""
        return self.id != other.id or self.snps != other.snps or self.model != other.state


def load_sam_file(samfile, chromosome):
    """
    Read data stored in a SAM file, convert it into NanoporeRead class objects.
    :param chromosome: (int) chromosome number
    :param samfile: (str) a sam file name
    :return: (list) a list of NanoporeRead instances
    """
    aligned_data = []
    file = open(samfile, "r")
    for line in file:
        if line.startswith("@"):  # ignore headers
            pass
        else:
            line = line.strip().split()
            end = int(line[3]) + len(line[9])
            if line[2].startswith("chr{}".format(chromosome)):
                read = NanoporeRead(line[0], line[2], line[9], line[3], end)
                aligned_data.append(read)
    file.close()
    return aligned_data


def get_overlapped_reads(reads, regions):
        """
        For a given sam file, find out if there is any READs in the file
        is located in human genetic imprinted regions.
        """
        overlapped_reads = []
        for read in reads:
            if read.if_in_imprinted_region(regions):
                overlapped_reads.append(read)
        return overlapped_reads


def reads_gt(reads, snps):
    """
    :param reads: list of Reads
    :param snps: list of SNPs
    """
    m_a = []
    m_b = []
    for read in reads:
        read.detect_snps(snps)
        read.detect_genotype()
        if read.gt == "1|0":
            m_a.append(read)
        elif read.gt == "0|1":
            m_b.append(read)
    return m_a, m_b
