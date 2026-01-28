import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/lunar_game_service.dart';
import '../services/vendor_service.dart';
import '../services/exploration_log_service.dart';
import '../models/vendor_item.dart';

class ShopScreen extends StatefulWidget {
  final String? difficultyLevel;
  final Function(String) onVisitComplete;

  const ShopScreen({
    super.key,
    this.difficultyLevel,
    required this.onVisitComplete,
  });

  @override
  State<ShopScreen> createState() => _ShopScreenState();
}

class _ShopScreenState extends State<ShopScreen> {
  bool _isSelling = false;
  String _statusMessage = '';

  @override
  Widget build(BuildContext context) {
    final vendorService = context.watch<VendorService>();
    final gameService = context.watch<LunarGameService>();
    final difficultyLevel = int.tryParse(widget.difficultyLevel ?? '1') ?? 1;
    final shopItems = vendorService.getShopItems(difficultyLevel);

    return Scaffold(
      backgroundColor: const Color(0xFF000000),
      appBar: AppBar(
        title: const Text(
          '◄ MOONLIGHT SHOP ►',
          style: TextStyle(
            fontFamily: 'Courier',
            fontSize: 18,
            color: Color(0xFFFFFFFF),
          ),
        ),
        backgroundColor: const Color(0xFF000000),
        foregroundColor: const Color(0xFFFFFFFF),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => handleExit(context),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildAsciiHeader(gameService),
            const SizedBox(height: 20),
            _buildModeToggle(),
            const SizedBox(height: 20),
            if (_isSelling) ..._buildSellSection(vendorService, gameService)
            else ..._buildBuySection(shopItems, vendorService, gameService),
            const SizedBox(height: 20),
            if (_statusMessage.isNotEmpty)
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  border: Border.all(color: const Color(0xFFFFD700)),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  _statusMessage,
                  style: const TextStyle(
                    fontFamily: 'Courier',
                    color: Color(0xFFFFD700),
                    fontSize: 14,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildAsciiHeader(LunarGameService gameService) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        border: Border.all(color: const Color(0xFF4A4A6A)),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '┌─────────────────────────────┐',
            style: TextStyle(
              fontFamily: 'Courier',
              color: Color(0xFF4A4A6A),
              fontSize: 14,
            ),
          ),
          const Text(
            '│     WELCOME TRAVELER       │',
            style: TextStyle(
              fontFamily: 'Courier',
              color: Color(0xFFFFD700),
              fontSize: 14,
            ),
          ),
          const Text(
            '│  I trade in moonlight and  │',
            style: TextStyle(
              fontFamily: 'Courier',
              color: Color(0xFF4A4A6A),
              fontSize: 14,
            ),
          ),
          const Text(
            '│  rare lunar artifacts...   │',
            style: TextStyle(
              fontFamily: 'Courier',
              color: Color(0xFF4A4A6A),
              fontSize: 14,
            ),
          ),
          Text(
            '│  Your moonlight: ${gameService.playerState.moonlight.toString().padLeft(4)}   │',
            style: const TextStyle(
              fontFamily: 'Courier',
              color: Color(0xFF00FF00),
              fontSize: 14,
            ),
          ),
          const Text(
            '└─────────────────────────────┘',
            style: TextStyle(
              fontFamily: 'Courier',
              color: Color(0xFF4A4A6A),
              fontSize: 14,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildModeToggle() {
    return Row(
      children: [
        Expanded(
          child: GestureDetector(
            onTap: () => setState(() => _isSelling = false),
            child: Container(
              padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
              decoration: BoxDecoration(
                border: Border.all(
                  color: _isSelling ? const Color(0xFF4A4A6A) : const Color(0xFFFFD700),
                ),
                color: _isSelling ? const Color(0xFF0F0F23) : const Color(0xFF1A1A2E),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                '◄ BUY ►',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontFamily: 'Courier',
                  color: _isSelling ? const Color(0xFF4A4A6A) : const Color(0xFFFFD700),
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: GestureDetector(
            onTap: () => setState(() => _isSelling = true),
            child: Container(
              padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
              decoration: BoxDecoration(
                border: Border.all(
                  color: _isSelling ? const Color(0xFFFFD700) : const Color(0xFF4A4A6A),
                ),
                color: _isSelling ? const Color(0xFF1A1A2E) : const Color(0xFF0F0F23),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                '◄ SELL ►',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontFamily: 'Courier',
                  color: _isSelling ? const Color(0xFFFFD700) : const Color(0xFF4A4A6A),
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }

  List<Widget> _buildBuySection(
    List<ShopItem> shopItems,
    VendorService vendorService,
    LunarGameService gameService,
  ) {
    if (shopItems.isEmpty) {
      return [
        const Text(
          'No items available at your current exploration depth.',
          style: TextStyle(
            fontFamily: 'Courier',
            color: Color(0xFF888888),
            fontSize: 14,
          ),
        ),
      ];
    }

    return [
      const Text(
        'AVAILABLE GOODS:',
        style: TextStyle(
          fontFamily: 'Courier',
          color: Color(0xFFFFD700),
          fontSize: 16,
          fontWeight: FontWeight.bold,
        ),
      ),
      const SizedBox(height: 10),
      ...shopItems.map((item) => _buildShopItem(item, vendorService, gameService)),
    ];
  }

  Widget _buildShopItem(ShopItem item, VendorService vendorService, LunarGameService gameService) {
    final canAfford = vendorService.canPurchaseItem(item);
    final inStock = item.currentStock > 0;
    
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(
          color: canAfford && inStock ? const Color(0xFF00FF00) : const Color(0xFF4A4A6A),
        ),
        borderRadius: BorderRadius.circular(4),
        color: const Color(0xFF0F0F23),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(
                  '${item.name} ${!inStock ? '[OUT]' : ''}',
                  style: TextStyle(
                    fontFamily: 'Courier',
                    color: canAfford && inStock ? const Color(0xFFFFFFFF) : const Color(0xFF888888),
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              Text(
                '${item.moonlightCost} ◆',
                style: TextStyle(
                  fontFamily: 'Courier',
                  color: canAfford ? const Color(0xFFFFD700) : const Color(0xFF888888),
                  fontSize: 14,
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            item.description,
            style: const TextStyle(
              fontFamily: 'Courier',
              color: Color(0xFFAAAAAA),
              fontSize: 12,
            ),
          ),
          if (inStock)
            Text(
              'Stock: ${item.currentStock}/${item.maxStock}',
              style: const TextStyle(
                fontFamily: 'Courier',
                color: Color(0xFF888888),
                fontSize: 11,
              ),
            ),
          const SizedBox(height: 8),
          if (canAfford && inStock)
            GestureDetector(
              onTap: () => _handlePurchase(item, vendorService),
              child: Container(
                padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
                decoration: BoxDecoration(
                  border: Border.all(color: const Color(0xFF00FF00)),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: const Text(
                  '◄ PURCHASE ►',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontFamily: 'Courier',
                    color: Color(0xFF00FF00),
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  List<Widget> _buildSellSection(VendorService vendorService, LunarGameService gameService) {
    final inventory = gameService.playerState.inventory;
    final sellableItems = inventory.entries.where((entry) => 
      VendorService.sellPrices.containsKey(entry.key) && entry.value > 0
    ).toList();

    if (sellableItems.isEmpty) {
      return [
        const Text(
          'SELLABLE ITEMS:',
          style: TextStyle(
            fontFamily: 'Courier',
            color: Color(0xFFFFD700),
            fontSize: 16,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 10),
        const Text(
          'No items to sell.',
          style: TextStyle(
            fontFamily: 'Courier',
            color: Color(0xFF888888),
            fontSize: 14,
          ),
        ),
      ];
    }

    return [
      const Text(
        'SELLABLE ITEMS:',
        style: TextStyle(
          fontFamily: 'Courier',
          color: Color(0xFFFFD700),
          fontSize: 16,
          fontWeight: FontWeight.bold,
        ),
      ),
      const SizedBox(height: 10),
      ...sellableItems.map((entry) => _buildSellableItem(entry.key, entry.value, vendorService)),
    ];
  }

  Widget _buildSellableItem(String itemId, int amount, VendorService vendorService) {
    final price = vendorService.getSellPrice(itemId);
    
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(color: const Color(0xFF4A4A6A)),
        borderRadius: BorderRadius.circular(4),
        color: const Color(0xFF0F0F23),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            '${itemId.replaceAll('_', ' ').toUpperCase()} x$amount',
            style: const TextStyle(
              fontFamily: 'Courier',
              color: Color(0xFFFFFFFF),
              fontSize: 14,
            ),
          ),
          Row(
            children: [
              Text(
                '$price ◆ each',
                style: const TextStyle(
                  fontFamily: 'Courier',
                  color: Color(0xFFFFD700),
                  fontSize: 12,
                ),
              ),
              const SizedBox(width: 16),
              GestureDetector(
                onTap: () => _handleSell(itemId, amount, vendorService),
                child: Container(
                  padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 12),
                  decoration: BoxDecoration(
                    border: Border.all(color: const Color(0xFF00FF00)),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: const Text(
                    'SELL ALL',
                    style: TextStyle(
                      fontFamily: 'Courier',
                      color: Color(0xFF00FF00),
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  void _handlePurchase(ShopItem item, VendorService vendorService) {
    final result = vendorService.purchaseItem(item);
    setState(() {
      _statusMessage = result ?? 'Purchase failed';
    });
    
    // Clear status message after 3 seconds
    Future.delayed(const Duration(seconds: 3), () {
      if (mounted) {
        setState(() {
          _statusMessage = '';
        });
      }
    });
  }

  void _handleSell(String itemId, int amount, VendorService vendorService) {
    final result = vendorService.sellItem(itemId, amount);
    setState(() {
      _statusMessage = result ?? 'Sale failed';
    });
    
    // Clear status message after 3 seconds
    Future.delayed(const Duration(seconds: 3), () {
      if (mounted) {
        setState(() {
          _statusMessage = '';
        });
      }
    });
  }

  void handleExit(BuildContext context) {
    final logService = context.read<ExplorationLogService>();

    // Add visit summary to log
    // TODO: Implement appendCustomEntry method
    // logService.appendCustomEntry(
    //   'SHOP VISIT',
    //   'You visited the mysterious moonlight shop. The hooded merchant nods as you leave, their wares shimmering with captured starlight.',
    //   {},
    // );

    // Resume exploration
    logService.resumeExploration();
    
    // Call completion callback
    widget.onVisitComplete('Shop visit completed');
    
    Navigator.of(context).pop();
  }
}