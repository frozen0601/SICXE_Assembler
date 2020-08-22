#search: !problem, **error**, [ALERT], [complete & checked]
import copy             #for ensuring deepcopy
import string           #I forgot
import re               #for parsing
import binascii         #for transforming character2hex
import pickle           #for saving pickle file
from pathlib import Path                #for path thing
from colorama import Fore, Back, Style  #for colorful error  

###GLOBALS###
ALPHA = string.ascii_letters
SBtable = {}
OPtable = {}
Pseudo = ["RESB", "RESW", "WORD", "END", "START", "BASE"]
Register = {'A' : "0", 
            'X' : "1",
            'L' : "2",
            'B' : "3",
            'S' : "4",
            'T' : "5",
            'F' : "6",
            'PC' : "8",
            'SW' : "9"}
intermediate = []   #Represent as a list for now
objectcode = ""     #Final result
curLine = 0         #For error report
hasBase = False     #determine if base exists
resbresw = False
baseOperand = 0     #Operand of base. Saved in pass 1 for pass 2 use.
prevLength = 0      #T's length to be add   e.g. '1E'
lineHead = 0        #Save T's starting location
blank = " "
nextLine = 0
modification = ""
#progStart = 0
StartPos = 0
errorCount = 0

###   the ises   ###
def isOP(mnemonic):             #check OPtable, return True if mnemonic found in OPtable
    return mnemonic in OPtable
def isPseudo(mnemonic):         #check PSEUDO, return True if mnemonic found in OPtable
    return mnemonic in Pseudo
def isLegit(line):              #line contains content
    return len(line) > 2
def hasLabel(line):
    return line[1][:1].isalpha()
def isSymbol(string):
    return string in SBtable.keys()
def isImmediate(string):
    if string != "":
        return string[0] == "#"
    else:
        return False
def isIndirect(string):
    return string[0] == "@"

### Little tools ###
def read(f):                    #Import program, return list
    raw = []
    with open(f, "r", encoding="utf8") as f:
        for line in f:
            raw.append(line)
    return raw
def importOP(f):                #Import OPtable
    with open(f, "r", encoding="utf8") as f:
        for line in f:
            line = line.split()
            key = line[0]
            if len(line) == 3:
                val = line[1], line[2]
            if len(line) == 4:  #if has r/rr distinguishing line
                val = line[1], line[2], line[3]
            OPtable[key] = val
def error(msg):
    global errorCount
    # print msg and abort the program
    errorCount += 1
    print(Fore.RED + "Error ", end='') #error
    print(Style.RESET_ALL, end='')
    print("on line", curLine,":", msg)
def translateXC(string):        #def makeLiteral(string): #Process X'' and C'' literal
    if string[0] == 'X':
        try:
            int(string[2:-1],16)
        except:
            error("Please use HEX with X format.")
            return "0"
        return string[2:-1]                 # Return hexadecimal string
    elif string[0] == 'C':
        if string[1] != "'" or string[-1] != "'":
            error("Please make sure you have operand in the right format. e.g. X'04' or C'EOF'.")
            return "0"
        else:
            return string[2:-1].encode().hex()
    else:
        error("le fuk ru doin? Only X or C accepted.")
        return "0"
def bare(x):                    #Get rid of "+, #, @"
    if x.startswith("+") or x.startswith("#") or x.startswith("@"):
        return x[1:]
    else:
        return x
def SearchSB(label):            #Check label's address
    return SBtable.get(label)
def add2mod(line):              #Add infos of modification record. For SIC/XE this only contains extended format
    global modification  
    global startPos
    modification += "\nM" + str(hex(line[1] + 1 - startPos))[2:].zfill(6) + blank + "05"

### Medium tools ###
def findOPformat(mnemonic):                     #Return format by searching OPtable. Doens't handle OP not found
    #if mnemonic == "RSUB":
    #    return 0
    if mnemonic in OPtable:
        result = OPtable.get(mnemonic)[1]
        if result == "1":
            return 1
        if result == "2":
            return 2
        if result == "3/4":
            return 3
    elif mnemonic[1:] in OPtable:
        if mnemonic[0] == '+':
            return 4
def formatting(input, output, curLine):         #Input type:str || output type:[] e.g. [7, 'COPY', 'START', '0']
    noComment = input
    nextStep = ""
    # get rid of comments & else.
    noComment = noComment.partition(".")[0]
    noComment = noComment.strip("\n").rstrip(" ").rstrip("\t").lstrip(" ").lstrip("\t")
    noComment = ' '.join(noComment.split())
    if ',' in noComment:
        
        noComment = re.sub(r'\s*,\s*', ',', noComment)
    
    if noComment.count(",") > 1:
        error("One sentence, one comma.")

    # if start with alphabet then preserve it
    if noComment.startswith(tuple(ALPHA)) or noComment.startswith("+"):
        nextStep = noComment
    #else:  # else make it a simple blank
    #    nextStep.append('')
    nextStep = re.split(' |\t', nextStep)
    #print(nextStep)

    # if the first value can't be found in OPtable or not a pseudo instruction, that's a label.
    formatted = nextStep
    if ( isOP(bare(nextStep[0])) or isPseudo(nextStep[0]) or nextStep[0] == 'RSUB'):
        formatted.insert(0, '')

    # RSUB can't have operand
    if len(nextStep) >= 2:
        if nextStep[1] == 'RSUB' and len(nextStep) > 2:
            error("RSUB can't have operand")

    formatted.insert(0, curLine)    #add
    output.append(formatted)
def lineLength(mnemonic, operand):              #return length of line from 0 ~ 4. For error case return -1
    global errorCount
    if mnemonic in ["START", "END", "BASE"]:
        return 0
    elif mnemonic == "RESB":
        #if operand[0] == 'X':
        #    return int(translateXC(operand), 16)               # Return number of hex bytes
        #if operand[0] == 'C':
        #    error("(RESB does not support character opperands)")
        #else:
        try:
            return int(operand)                                # Return number of decimal bytes
        except:
            error("You shouldn't use value other then decimal.")  #like using HEX or else
            return 0
    elif mnemonic == "RESW":
        #if operand[0] == 'X':
        #    return int(translateXC(operand), 16) * 3           # Return number of hex words
        #if operand[0] == 'C':
        #    error("(RESW does not support character opperands)")
        #else:
        try:
            return int(operand) * 3                            # Return number of decimal words
        except:
            error("You shouldn't use value other then decimal.")  #like using HEX or else
            return 0

    elif mnemonic == "WORD":
        try:
            int(operand)
        except:
            error("You shouldn't use value other then decimal.")  #like using HEX or else
            return 0
        return 3

    elif mnemonic == "BYTE":
        if operand == "X''" or operand == "C''":
            error("BYTE must be given with value")
            return -1        
        try:
            if operand[0] == 'X':
                if operand[1] != "'" or operand[-1] != "'":   
                    #error("Please make sure you have operand in the right format. e.g. X'04' or C'EOF'.")
                    return -1
                if len(operand[2:-1]) % 2 != 0:   #only accept byte-sized decimal
                    error("Only byte-sized HEX can be used with BYTE X'_ _' format.")
                    try:
                        int(operand[2:-1],16)
                    except:
                        error("Please use HEX with X format.")
                    return -1
            return len(translateXC(operand))/2
        
        except:
            error("BYTE must be given with an operand")
            return -1

    elif bare(mnemonic) in OPtable:        #yeah?
        return findOPformat(mnemonic)

    else:
        errorCount += 1
        #print(Fore.RED + "Error ", end='')
        #print(Style.RESET_ALL, end='')
        #print("on line", curLine,":", "Mnemonic undefined:", bare(mnemonic)) #error
        error("Mnemonic undefined")
        return -1   #unknown mnemonic
def assembleLine(opcode, nixbpe, disp, type):   #Tested with immediate(#int) only. opcode: '3C' nixbpe: '110010'  disp: '123'  type: "normal" or "extend"
    opcode = int(opcode, 16)
    if type == "type3":    #length = 3 bytes
        ni = int(nixbpe[:2], 2)         #ni
        xbpe = int(nixbpe[2:], 2)
        section1 = hex(opcode + ni)[2:].zfill(2)
        section2 = str(hex(xbpe))[2:]  #x
        section3 = hex(int(disp))[2:].zfill(3)
        return section1 + section2 + section3

    if type == "type4":
        ni = int(nixbpe[:2], 2)
        xbpe = int(nixbpe[2:], 2)
        section1 = hex(opcode + ni)[2:].zfill(2)
        section2 = str(hex(xbpe))[2:]  #x
        section3 = hex(int(disp))[2:].zfill(5)
        return section1 + section2 + section3


    #    pass
def baseORpc(location, pc):                     #Return 1. (location - PC) 2. (location - BASE) 3. Error: return "0"
    if -2048 <= location - pc < 2048:       #use PC
        if location - pc >= 0:
            return "PC", str(location - pc)
        else:
            return "PC", str(location - pc + 4096)  #add 4096 for negative value  
    elif hasBase:
        if 0 <= location - int(SBtable.get("BASE")) < 4096: 
            return "BASE", str(location - int(SBtable.get("BASE")))  #use BASE
    else:
        error("Instruction addressing error")
        return "error", str(0)
def addObjectcode(line, thisLineCode):          #Line: intermediate file raw line (for whole T's length calculation use).    #thisLineCode: its object code
    global objectcode
    global prevLength
    global lineHead
    global nextLine
    global resbresw
    #T 001000 1E 141033 482039 001036 ...
    if nextLine[1] - lineHead <= 30 and not resbresw:
        objectcode += thisLineCode + blank
        prevLength = nextLine[1] - lineHead
    else:   #too long, create new line
        i = objectcode.rfind("T") + 6   #find where to insert linesize
        objectcode = objectcode[:i+1] + blank + hex(prevLength)[2:].zfill(2) + blank + objectcode[i+1:]
        lineHead = line[1]
        objectcode += "\nT" + hex(lineHead)[2:].zfill(6) + thisLineCode + blank  
        prevLength = nextLine[1] - lineHead             #[ALERT] remember to insert linelength after linHead
    resbresw = False

###     PASS     ###
def pass1():
    ########box of chaos########
    formatted = []  #a raw, formatted
    curLoc = 0
    startflag = False
    endflag = False
    global curLine
    global hasBase
    global errorCount
    ############################
    for i in range(len(raw)):
        curLine += 1    #for error report
        #[1] Formatting
        formatting(raw[i], formatted, curLine)  #(input, output, linetag)   
        #output: formatted = [[1, ''], [2, '']...[7, 'COPY', 'START', '0']...[60, '', 'END', 'FIRST'], [61, ''], [62, '']]
        line = formatted[i]         #line format: [curLine, label...]
        
        #[2] SBtable/location
        #[2.1] Build SBtable
        if isLegit(line):           #then should start doing things
            if line[2] == "START":
                try:
                    curLoc = int(line[3],16)
                except:
                    curLoc = 0
                    error("Only HEX address accepted for START. Location set to 0")  #like using HEX or else
                line.insert(1, int(curLoc))
                startflag = True
                intermediate.append(line)
                continue

            elif hasLabel(line):    #then prepare to add it to SBtable
                label = line[1]
                #bare(label)         #might not be necessary
                if isSymbol(label):
                    error("Symbol " + label + " redefined. Symbol updated with new location.")    
                SBtable[label] = int(curLoc)
    
        #[2.2] Add location info/ Save BASE location
            if len(line) == 3:  #no operand -> RSUB
                mnemonic, operand = line[2], 0
            else:
                mnemonic, operand = line[2], line[3]
            
            line.insert(1, int(curLoc))                 #line format: [curLine, curLoc, label...]
            ll = lineLength(mnemonic, operand)
            if ll == -1:     #**error** handled: mnemonic error
                continue
            curLoc += ll 

            if line[3] == "BASE":   #search for BASE. Saves its operand's location
                global baseOperand
                baseOperand = line[4]
    
        #[2.3] Add opcode
            if bare(mnemonic) in OPtable:          ##line format: [curLine, curLoc, label..., opcode]
                line.append(OPtable.get(bare(mnemonic))[0])             #bare returns mnemonic without "+@#" ahead
    
        #[2.4] postprocesses
            if line[3] == 'END':
                endflag = True

            if startflag == True:
                if endflag == False or line[3] == 'END':
                    if len(line) > 6:
                        error("TOO LONG, I don't think it'll fit")
                    else:
                        intermediate.append(line)
                else:
                    error("PROG must ends with 'END'")
            else:
                error("PROG must starts with 'START'")
          
    with open(Path(__file__).parent.joinpath('106213076黃暐澄_intermediate'), 'wb') as fp:    #save file to same directory as .py file
        pickle.dump(intermediate, fp)
def pass2(intermediate):
    ########box of chaos########
    global startPos
    global objectcode
    global SBtable
    global hasBase
    global curLine
    global lineHead
    global blank
    global nextLine
    global errorCount
    global resbresw
    lineFormat = 0
    startPos = intermediate[0][1]
    programSize = intermediate[-1][1] - intermediate[0][1]      ##watch out for lines before start
    #global progStart    #duplicate with startPos
    ############################
    if baseOperand in SBtable:  #else hasBase remains False
        SBtable["BASE"] = SBtable.get(baseOperand)
        hasBase = True

    for i in range(len(intermediate)):
        if i < len(intermediate) - 1:
            nextLine = intermediate[i + 1]  # nextLine: for calculating when to create new T
        line = intermediate[i]              #[RECAP] line format: [curLine, curLoc, label, mnemonic, operand]
        curLine = line[0]                   #for debug
        thisLineCode = ""
        #print("line", line)

        if line[3] == "END":
            #Add modification record
            objectcode += modification      
            #then the END itself
            i = objectcode.rfind("T") + 7   #find where to insert the last T's linesize
            objectcode = objectcode[:i] + blank + hex(prevLength)[2:].zfill(2) + blank + objectcode[i:]

            for j in range(len(intermediate)):
                if line[4] == intermediate[j][2]:
                    endPos = intermediate[j][1]
                    break
            objectcode += "\nE" + hex(endPos)[2:].zfill(6)
            break
        if line[3] == "START":
            #progStart = copy.deepcopy(startPos)
            objectcode += "H" + line[2].ljust(6, ' ') + blank + hex(startPos)[2:].zfill(6) + blank + hex(programSize)[2:].zfill(6) #(mnemonic, operand, curLoc)
            objectcode += "\nT" + hex(startPos)[2:].zfill(6)
            lineHead = startPos 
            continue
        
        if intermediate[i - 1][3] == "RESB" or intermediate[i - 1][3] == "RESW":
            resbresw = True
        pc = intermediate[i + 1][1]    #(head & tail), SHOULD be safe( avoiding out of range)
        lineFormat = findOPformat(line[3])  #return byte 1, 2, 3/4

        #thisLength += lineFormat
        #if thisLength <= 30:
        #    pass
        #else:   #too long, create new line
        #    objectcode += "\n"

        if line[3] == "BYTE":
            if line[4][0] in ["X", "C"]:
                addObjectcode(line, translateXC(line[4]))
                continue
            else:
                try:
                    addObjectcode(line,hex(int(line[4]))[2:].zfill(2))
                except:
                    pass
                continue

        if line[3] == "WORD":
            if line[4][0] in ["X", "C"]:
                addObjectcode(line, translateXC(line[4]))
                continue
            else:
                try:
                    int(line[4])
                except:
                    error("You shouldn't use value other then decimal.")
                    continue
                addObjectcode(line,hex(int(line[4]))[2:].zfill(6))
                continue
        
        if lineFormat == 1:                                
            addObjectcode(line, hex(opcode)[2:].zfill(2))
            continue

        elif lineFormat == 2:       #[complete & checked]
            if (line[-3] == "SVC"): #SVC has no operand. [ALERT] not fully complete, do i have to do this?
                addObjectcode(line, line[-1] + "00")
                continue
            mnemonic, operand, opcode = line[-3], line[-2], line[-1]
            if OPtable.get(mnemonic)[-1] == "r":    #SBtable.get(mnemonic)[-1] ----> r/rr/others
                if Register.get(operand) is None:
                    error("Operand must be a register.")
                    continue
                addObjectcode(line, line[-1] + Register.get(operand) + "0")
                continue
            elif OPtable.get(mnemonic)[-1] == "rr": #op + register from "X" before "," + register from "y" after ","
                try:
                    operand12 = operand.split(',')
                    if Register.get(operand12[0]) is None or Register.get(operand12[1]) is None:
                        error("Both operands must be register.")
                        continue
                    addObjectcode(line, line[-1] + Register.get(operand12[0]) + Register.get(operand12[1]))
                    continue
                except:
                    error("Two registers required.")
            #else:

        elif lineFormat == 3 or lineFormat == 4:  #3/4
            mnemonic, operand, opcode = line[3], line[4], line[-1]
            #print("mnemonic, operand: ",mnemonic, operand)
        #(1)Immediate(operand have "#"):     
            if isImmediate(operand):                            #[nixbpe = 010??0][nix = 010], indexed addressing is not supported for Indirect and Immediate addressing modes
                if bare(operand)[0].isdigit():                  #if after # is integer: 010000          #[nixbpe = 010000][bp = 00]
                    if 0 <= int(bare(operand)) < 4096:
                        disp = bare(operand)
                        thisLineCode = assembleLine(opcode, "010000", disp, "type3")
                        addObjectcode(line, thisLineCode)
                        continue
                    elif 4096 <= int(bare(operand)) < 1048576 and mnemonic.startswith("+"):  #extended  #[complete & checked]
                        disp = int(bare(operand))
                        thisLineCode = assembleLine(opcode, "010001", disp, "type4")
                        addObjectcode(line, thisLineCode)
                        continue
                    else:
                        error("Immediate number out of range")
                        continue

            if mnemonic != "RSUB":
                if mnemonic.startswith("+"):
                    add2mod(line)
                    if operand.startswith("@"):
                        disp = SBtable.get(operand)
                        if disp is None:
                            errorCount += 1
                            print(Fore.RED + "Error ", end='') #error
                            print(Style.RESET_ALL, end='')
                            print("on line", curLine,":", "undefined symbol:", bare(operand)) #error
                            #error("Symbol undefined")
                            continue
                        thisLineCode = assembleLine(opcode, "100001", disp, "type4")    #???
                        addObjectcode(line, thisLineCode)
                        continue
                    else:      
                        disp = SBtable.get(operand)
                        if disp is None:
                            errorCount += 1
                            print(Fore.RED + "Error ", end='') #error
                            print(Style.RESET_ALL, end='')
                            print("on line", curLine,":", "undefined symbol:", bare(operand)) #error
                            #error("Symbol undefined")
                            continue
                        thisLineCode = assembleLine(opcode, "110001", disp, "type4")
                        addObjectcode(line, thisLineCode)
                        continue
                #(3.1)normal [x = 1]
                operandx = ""
                if "," in operand:
                    operandx = copy.deepcopy(operand)   #operand with index
                    #operand = operand[:-2]
                    operand = operandx.split(',')[0]
                    operand2 = operandx.split(',')[-1]
                if bare(operand) in SBtable:
                    basepcFlag ,disp = baseORpc(SBtable.get(bare(operand)), pc)  #SBtable.get(bare(operand)) -> return SBtable location
                    if basepcFlag == "PC":
                        nixbpe = "110010"
                        if operand.startswith("#"): #ni = 01
                            nixbpe = "010010"
                        if operand.startswith("@"): #nix = 100
                            nixbpe = "100010"
                        if "," in operandx:          #needn't have to have base nor pc
                            if Register.get(operand2) is None:
                                error("In indexed addressing, the second operand must be a register.")
                                continue
                            nixbpe = "111010"
                            thisLineCode = assembleLine(opcode, nixbpe, baseORpc(SBtable.get(bare(operand)), pc)[1], "type3")
                            addObjectcode(line, thisLineCode)
                            continue
                        thisLineCode = assembleLine(opcode, nixbpe, disp, "type3")
                        addObjectcode(line, thisLineCode)
                        continue
                    elif basepcFlag == "BASE":  
                        nixbpe = "110100"
                        if operand.startswith("#"): #ni = 01
                            nixbpe = "010100"
                        if operand.startswith("@"): #ni = 10
                            nixbpe = "100100"
                        if "," in operandx:          #x = 1  111??0
                            #meh =   + SBtable.get(operand[operand.find(",") + 1:]) #operand[:operand.find(",")]: things ahead ","
                            if Register.get(operand2) is None:
                                error("In indexed addressing, the second operand must be a register.")
                                continue
                            nixbpe = "111100"
                            thisLineCode = assembleLine(opcode, nixbpe, disp, "type3")
                            addObjectcode(line, thisLineCode)
                            continue
                        thisLineCode = assembleLine(opcode, nixbpe, disp, "type3")
                        addObjectcode(line, thisLineCode)
                        continue
                    elif basepcFlag == "error":
                        continue
                else:
                    errorCount += 1
                    print(Fore.RED + "Error ", end='') #error
                    print(Style.RESET_ALL, end='')
                    print("on line", curLine,":", "undefined symbol:", bare(operand)) #error
                    continue
            
            #??99% this is RSUB ( maybe more)
            else:
                if operand.startswith("@"):
                    thisLineCode = assembleLine(opcode, "100000", "0", "type3") #???
                    addObjectcode(line, thisLineCode)
                    continue
                else:    
                    thisLineCode = assembleLine(opcode, "110000", "0", "type3")
                    addObjectcode(line, thisLineCode)
                    continue

    #PEACE
    objectcode = objectcode.upper()           
    with open(Path(__file__).parent.joinpath('106213076黃暐澄_output.txt'), 'w') as f:
        f.write(objectcode)

def main():
    pass1() ### pass 1 ###
    #print("******SBtable*******")
    #print(SBtable)
    #print("******OPtable*******")
    #print(OPtable)

    #with open(Path(__file__).parent.joinpath('106213076黃暐澄_intermediate'), 'rb') as fp:
    #    intermediate = pickle.load(fp)

    #print("\nintermediate:")
    #for i in range(len(intermediate)):
    #    print(intermediate[i])

    pass2(intermediate) ### pass 2 ###
    if errorCount == 0:
        print("\nintermediate:")
        for i in range(len(intermediate)):
            print(intermediate[i])
        print("\nobjectcode:")
        print(objectcode)

raw = read(input("input program file name or path((test)SICXE.asm): "))
importOP(Path(__file__).parent.joinpath('xeopCode.txt'))
#importOP(input("input OPtable file name or path(opCode.txt): ")) 
main()