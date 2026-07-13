"""
score7_emu/cpu.py — Squelette du cœur CPU Sunplus/GeneralPlus S+core7 (Score7).

But de ce fichier : poser la structure minimale et correcte de l'émulateur,
PAS implémenter tous les opcodes (ça viendra fonction par fonction, au fur
et à mesure qu'on les désassemble depuis Lead.sys et les .wxn).

Rappel de l'algorithme de décodage confirmé (cf CLAUDE.md, section 2) :
    - lire un halfword (16 bits) "low" à PC
    - si bit15(low) == 0        -> instruction 16 bits simple, PC += 2
    - si bit15(low) == 1 :
        - lire le halfword "high" à PC+2
        - si bit15(high) == 1   -> instruction 32 bits (low+high forment le mot,
                                     avec dépouillement de parité), PC += 4
        - si bit15(high) == 0   -> PCE : deux instructions 16 bits en parallèle
                                     (low et high sont chacune une instr complète), PC += 4

Ce module ne connaît PAS encore le détail des champs internes de chaque
instruction (registres source/dest, immédiats, etc.) — seulement la taille.
La table OPCODES sera remplie opcode par opcode, avec la fonction de décodage
exacte, une fois chaque instruction confirmée via le désassembleur validé
(cf. la session précédente : validation croisée sur les cibles de branchement).
"""

from dataclasses import dataclass, field


NUM_GPR = 32


@dataclass
class Registers:
    """Banque de registres généraux + PC + registres spéciaux connus à ce stade.

    sr0 : vu dans la section .mxb comme compteur de répétition d'une boucle
          de copie mémoire (lhu/sh puis lw/sw) -> probablement un registre
          "count"/"loop" dédié, pas un GPR classique. À confirmer.
    cr  : registre de condition/status, hypothèse standard RISC (flags Z/C/N/V).
          Existence et layout exact non confirmés — placeholder.
    """
    gpr: list = field(default_factory=lambda: [0] * NUM_GPR)
    pc: int = 0
    lr: int = 0      # link register (hypothèse, usage probable pour jl/jal)
    sr0: int = 0      # registre compteur observé dans .mxb — rôle exact à confirmer
    cr: int = 0       # condition register — placeholder, layout non confirmé

    def __getitem__(self, i):
        if i == 0:
            return 0  # convention RISC courante : r0 câblé à zéro (à vérifier pour Score7)
        return self.gpr[i]

    def __setitem__(self, i, value):
        if i == 0:
            return
        self.gpr[i] = value & 0xFFFFFFFF


class Bus:
    """Bus mémoire/MMIO. Rien de spécifique au SPG293 n'est mappé pour l'instant :
    seulement un backing RAM générique + un point d'extension pour les
    registres matériels (vidéo, son SP_ToneMaker, DMA, timers, GPIO — cf.
    priorité listée dans CLAUDE.md, section 3, portée "émulateur propre").
    """

    def __init__(self, size=0x2000000):
        self.ram = bytearray(size)
        # table d'I/O mappée : {adresse_base: (read_fn, write_fn)} à peupler
        # au fur et à mesure qu'on identifie les registres MMIO (ex: celui
        # touché par Deciphering_Data_And_DMA, bit OR 1 / AND 0xFFFE observé).
        self.mmio_handlers = {}

    def load_elf_segment(self, data: bytes, vaddr: int):
        end = vaddr + len(data)
        if end > len(self.ram):
            raise ValueError("segment hors de la RAM allouée, agrandir Bus(size=...)")
        self.ram[vaddr:end] = data

    def read16(self, addr: int) -> int:
        return int.from_bytes(self.ram[addr:addr + 2], "little")

    def read32(self, addr: int) -> int:
        return int.from_bytes(self.ram[addr:addr + 4], "little")

    def write16(self, addr: int, value: int):
        self.ram[addr:addr + 2] = (value & 0xFFFF).to_bytes(2, "little")

    def write32(self, addr: int, value: int):
        self.ram[addr:addr + 4] = (value & 0xFFFFFFFF).to_bytes(4, "little")


class Score7CPU:
    def __init__(self, bus: Bus):
        self.bus = bus
        self.regs = Registers()
        self.halted = False
        # table d'opcodes à peupler progressivement : {mask/pattern: handler}
        # volontairement vide pour l'instant — voir docstring du module.
        self.opcode_table = {}

    def fetch_instruction_words(self):
        """Retourne (kind, words, size) sans PC += appliqué, kind in
        {"16", "32", "pce"}. Ne décode pas encore les champs internes."""
        pc = self.regs.pc
        low = self.bus.read16(pc)
        if (low & 0x8000) == 0:
            return "16", (low,), 2
        high = self.bus.read16(pc + 2)
        if (high & 0x8000) != 0:
            return "32", (low, high), 4
        return "pce", (low, high), 4

    def step(self):
        """Exécute une instruction. Ne fait rien de réel tant que
        opcode_table n'est pas peuplée -- lève NotImplementedError pour
        rendre visible immédiatement ce qui manque, plutôt que d'avancer
        silencieusement sur du faux."""
        kind, words, size = self.fetch_instruction_words()
        raise NotImplementedError(
            f"Décodage non implémenté: PC={self.regs.pc:#x} kind={kind} words={[hex(w) for w in words]}. "
            f"Ajouter le handler correspondant dans opcode_table."
        )
        # self.regs.pc += size  # à activer une fois l'exécution réelle branchée

    def run(self, max_steps=1):
        for _ in range(max_steps):
            if self.halted:
                break
            self.step()